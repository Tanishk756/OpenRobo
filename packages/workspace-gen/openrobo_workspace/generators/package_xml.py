"""Package XML (REP-149) generator for bringup package (Hardened)."""

import re
from xml.sax.saxutils import escape

from openrobo_workspace.models import GeneratedFile, WorkspaceGenerationPlan

ROS_PKG_NAME_REGEX = re.compile(r"^[a-z][a-z0-9_]*$")


def validate_ros_package_name(name: str) -> bool:
    """Check if name conforms to standard ROS 2 package naming rules."""
    return bool(ROS_PKG_NAME_REGEX.match(name)) and not name.startswith("_") and not name.endswith("_")


def generate_package_xml(plan: WorkspaceGenerationPlan) -> GeneratedFile:
    pkg_name = plan.bringup_package_name
    if not validate_ros_package_name(pkg_name):
        raise ValueError(f"Invalid ROS 2 package name '{pkg_name}'. Must match ^[a-z][a-z0-9_]*$")

    escaped_pkg_name = escape(pkg_name)
    escaped_desc = escape(plan.description or "Automated bringup and runtime meta-package for OpenRobo stack.")

    # Maintainer formatting (REP-149 requires a valid email and non-empty name)
    maintainer_name = plan.maintainer.name if (plan.maintainer and plan.maintainer.name) else "OpenRobo Generated Workspace"
    maintainer_email = plan.maintainer.email if (plan.maintainer and plan.maintainer.email) else "unspecified@placeholder.openrobo"
    escaped_m_name = escape(maintainer_name)
    escaped_m_email = escape(maintainer_email)

    # Collect explicit ROS package exec_depends only
    exec_depends = []
    unmapped_depends = []

    for c in sorted(plan.components, key=lambda x: x.resource_id):
        if c.ros_package_names:
            for rpkg in sorted(set(c.ros_package_names)):
                if validate_ros_package_name(rpkg):
                    exec_depends.append(f"  <exec_depend>{escape(rpkg)}</exec_depend>")
                else:
                    unmapped_depends.append(f"  <!-- Resource '{c.resource_id}' invalid ROS package name: '{rpkg}' -->")
        elif c.has_adapter and c.adapter_name:
            # Verified canonical adapter packages
            adapter_default_pkgs = {
                "nav2": ["nav2_bringup"],
                "slam_toolbox": ["slam_toolbox"],
                "ros2_control": ["controller_manager"],
                "gazebo": ["ros_gz_sim", "ros_gz_bridge"],
            }
            for ad_pkg in adapter_default_pkgs.get(c.adapter_name, []):
                exec_depends.append(f"  <exec_depend>{escape(ad_pkg)}</exec_depend>")
        else:
            unmapped_depends.append(f"  <!-- Resource '{c.resource_id}' has no verified ROS package mapping -->")

    all_depends = exec_depends + unmapped_depends
    exec_depends_str = "\n".join(all_depends) if all_depends else "  <!-- No explicit package dependencies -->"

    xml_text = f"""<?xml version="1.0"?>
<?xml-model href="http://download.ros.org/schema/package_format3.xsd" schematypens="http://www.w3.org/2001/XMLSchema"?>
<package format="3">
  <name>{escaped_pkg_name}</name>
  <version>1.0.0</version>
  <description>{escaped_desc}</description>
  <maintainer email="{escaped_m_email}">{escaped_m_name}</maintainer>
  <license>Apache-2.0</license>

  <buildtool_depend>ament_cmake</buildtool_depend>

{exec_depends_str}

  <test_depend>ament_lint_auto</test_depend>
  <test_depend>ament_lint_common</test_depend>

  <export>
    <build_type>ament_cmake</build_type>
  </export>
</package>
"""
    return GeneratedFile(
        path=f"src/{pkg_name}/package.xml",
        content=xml_text,
        description=f"REP-149 compliant ROS 2 package manifest for {pkg_name}",
    )
