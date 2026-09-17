"""Execution Providers for OpenRobo."""

from openrobo_runtime.providers.base import ExecutionProvider
from openrobo_runtime.providers.detector import ProviderDetector
from openrobo_runtime.providers.docker import DockerProvider
from openrobo_runtime.providers.local import LocalProcessProvider
from openrobo_runtime.providers.podman import PodmanProvider

__all__ = [
    "ExecutionProvider",
    "DockerProvider",
    "LocalProcessProvider",
    "PodmanProvider",
    "ProviderDetector",
]
