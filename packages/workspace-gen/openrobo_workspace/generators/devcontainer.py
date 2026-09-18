"""VS Code Dev Container generator."""

import json

from openrobo_workspace.models import GeneratedFile, WorkspaceGenerationPlan


def generate_devcontainer_json(plan: WorkspaceGenerationPlan) -> GeneratedFile:
    config = {
        "name": f"OpenRobo Dev Container ({plan.stack_name})",
        "dockerComposeFile": ["../docker/docker-compose.yml"],
        "service": "robot",
        "workspaceFolder": "/openrobo_ws",
        "customizations": {
            "vscode": {
                "extensions": [
                    "ms-iot.vscode-ros",
                    "ms-vscode.cpptools",
                    "ms-python.python",
                    "redhat.vscode-yaml",
                    "redhat.vscode-xml",
                ],
                "settings": {
                    "ros.rosDistro": plan.target_distro,
                    "terminal.integrated.defaultProfile.linux": "bash",
                },
            }
        },
        "remoteUser": "root",
    }

    return GeneratedFile(
        path=".devcontainer/devcontainer.json",
        content=json.dumps(config, indent=2) + "\n",
        description="VS Code Remote Containers development environment definition",
    )
