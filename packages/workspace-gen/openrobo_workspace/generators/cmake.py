"""CMakeLists.txt generator for bringup package."""

from openrobo_workspace.models import GeneratedFile, WorkspaceGenerationPlan


def generate_cmake(plan: WorkspaceGenerationPlan) -> GeneratedFile:
    content = f"""cmake_minimum_required(VERSION 3.8)
project({plan.bringup_package_name})

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Find ament_cmake buildtool
find_package(ament_cmake REQUIRED)

# Install launch and config trees into share directory
install(
  DIRECTORY launch config
  DESTINATION share/${{PROJECT_NAME}}
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
"""
    return GeneratedFile(
        path=f"src/{plan.bringup_package_name}/CMakeLists.txt",
        content=content,
        description=f"CMakeLists.txt build specification for {plan.bringup_package_name}",
    )
