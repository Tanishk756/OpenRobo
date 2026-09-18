"""Static Generated-Workspace Validator.

Performs deterministic static analysis on generated workspace artifacts
(XML, Python AST, YAML, JSON, ROS naming, file references).
Distinguishes static syntax/structure validation from actual runtime execution.
"""

import ast
import json
import re
import xml.etree.ElementTree as ET
from typing import List, Optional

import yaml

from openrobo_workspace.models import (
    ExecutionStatus,
    GeneratedFile,
    WorkspaceGenerationPlan,
    WorkspaceValidationResult,
)

ROS_PKG_REGEX = re.compile(r"^[a-z][a-z0-9_]*$")


class WorkspaceValidator:
    """Performs static syntax and structural validation on generated workspace files."""

    @classmethod
    def validate_files(
        cls,
        files: List[GeneratedFile],
        plan: Optional[WorkspaceGenerationPlan] = None,
    ) -> WorkspaceValidationResult:
        errors: List[str] = []
        warnings: List[str] = []
        checks_performed = 0

        file_map = {f.path: f.content for f in files}

        # Check for duplicate/normalized path conflicts
        seen_paths = set()
        for f in files:
            norm = f.path.replace("\\", "/").strip().lower()
            if norm in seen_paths:
                errors.append(f"Duplicate generated file path detected: '{f.path}'")
            seen_paths.add(norm)

        # 1. Validate package.xml
        package_xml_files = [f for f in files if f.path.endswith("package.xml")]
        for pxml in package_xml_files:
            checks_performed += 1
            try:
                root = ET.fromstring(pxml.content)
                if root.tag != "package":
                    errors.append(f"{pxml.path}: Root element must be <package>, found <{root.tag}>")
                name_elem = root.find("name")
                if name_elem is None or not name_elem.text:
                    errors.append(f"{pxml.path}: Missing required <name> element")
                else:
                    pkg_name = name_elem.text.strip()
                    if not ROS_PKG_REGEX.match(pkg_name):
                        errors.append(
                            f"{pxml.path}: Package name '{pkg_name}' violates ROS 2 naming conventions"
                        )
                maintainer_elem = root.find("maintainer")
                if maintainer_elem is None:
                    errors.append(f"{pxml.path}: Missing required <maintainer> element")
                else:
                    email = maintainer_elem.get("email", "")
                    if "placeholder" in email.lower() or "unspecified" in email.lower():
                        warnings.append(
                            f"{pxml.path}: Maintainer email is a placeholder ('{email}')."
                        )
                license_elem = root.find("license")
                if license_elem is None:
                    errors.append(f"{pxml.path}: Missing required <license> element")
            except ET.ParseError as e:
                errors.append(f"{pxml.path}: Invalid XML syntax: {e}")

        # 2. Validate CMakeLists.txt
        cmakelists_files = [f for f in files if f.path.endswith("CMakeLists.txt")]
        for cmake in cmakelists_files:
            checks_performed += 1
            content = cmake.content
            if "cmake_minimum_required" not in content:
                errors.append(f"{cmake.path}: Missing cmake_minimum_required declaration")
            if "find_package(ament_cmake REQUIRED)" not in content:
                errors.append(f"{cmake.path}: Missing find_package(ament_cmake REQUIRED)")

        # 3. Validate Python Launch Files (AST parsing)
        py_files = [f for f in files if f.path.endswith(".py")]
        for pyf in py_files:
            checks_performed += 1
            try:
                ast.parse(pyf.content, filename=pyf.path)
            except SyntaxError as e:
                errors.append(f"{pyf.path}: Python AST syntax error at line {e.lineno}: {e.msg}")

        # 4. Validate YAML Files (safe load)
        yaml_files = [f for f in files if f.path.endswith((".yaml", ".yml"))]
        for yf in yaml_files:
            checks_performed += 1
            try:
                parsed = yaml.safe_load(yf.content)
                if parsed is None and len(yf.content.strip()) > 0:
                    warnings.append(f"{yf.path}: Empty YAML document")
            except yaml.YAMLError as e:
                errors.append(f"{yf.path}: Invalid YAML syntax: {e}")

        # 5. Validate JSON Files
        json_files = [f for f in files if f.path.endswith(".json")]
        for jf in json_files:
            checks_performed += 1
            try:
                json.loads(jf.content)
            except json.JSONDecodeError as e:
                errors.append(f"{jf.path}: Invalid JSON syntax at line {e.lineno}: {e.msg}")

        # 6. Validate Shell scripts (check for null bytes and proper shebang)
        sh_files = [f for f in files if f.path.endswith(".sh")]
        for sh in sh_files:
            checks_performed += 1
            if "\x00" in sh.content:
                errors.append(f"{sh.path}: Shell script contains null byte character")
            if not sh.content.startswith("#!/"):
                warnings.append(f"{sh.path}: Shell script missing shebang header")

        # 7. Check file references if plan is supplied
        if plan:
            checks_performed += 1
            # Verify bringup package exists in files
            bringup_pkg = plan.bringup_package_name
            expected_pxml = f"src/{bringup_pkg}/package.xml"
            if expected_pxml not in file_map:
                errors.append(f"Expected bringup package.xml at '{expected_pxml}' was not generated")

        is_valid = len(errors) == 0
        status = ExecutionStatus.PASSED if is_valid else ExecutionStatus.FAILED

        return WorkspaceValidationResult(
            is_valid=is_valid,
            status=status,
            checks_count=checks_performed,
            errors=errors,
            warnings=warnings,
        )
