"""Package XML (REP-149) generator for bringup package."""

from openrobo_workspace.models import GeneratedFile, WorkspaceGenerationPlan


def generate_package_xml(plan: WorkspaceGenerationPlan) -> GeneratedFile:
    exec_depends = []
    for c in sorted(plan.components, key=lambda x: x.resource_id):
        pkg_name = c.resource_id.split("/")[-1].replace("-", "_")
        exec_depends.append(f"  <exec_depend>{pkg_name}</exec_depend>")

    exec_depends_str = "\n".join(exec_depends) if exec_depends else "  <!-- No explicit package dependencies -->"

    xml_text = f"""<?xml version="1.0"?>
<?xml-model href="http://download.ros.org/schema/package_format3.xsd" schematypens="http://www.w3.org/2001/XMLSchema"?>
<package format="3">
  <name>{plan.bringup_package_name}</name>
  <version>1.0.0</version>
  <description>{plan.description or "Automated bringup and runtime meta-package for OpenRobo stack."}</description>
  <maintainer email="maintainer@openrobo.org">OpenRobo Core Team</maintainer>
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
        path=f"src/{plan.bringup_package_name}/package.xml",
        content=xml_text,
        description=f"REP-149 compliant ROS 2 package manifest for {plan.bringup_package_name}",
    )
