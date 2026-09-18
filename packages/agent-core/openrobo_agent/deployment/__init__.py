"""Local A/B workspace slot manager, staging, atomic activation, rollback, and remote deployment worker."""

from openrobo_agent.deployment.activation import activate_staged_slot
from openrobo_agent.deployment.artifact_client import ArtifactClient, ArtifactVerificationError, SSRFValidationError
from openrobo_agent.deployment.models import ActivationIntent, SlotMetadata, SlotsState, SlotState
from openrobo_agent.deployment.rollback import rollback_to_previous
from openrobo_agent.deployment.slots import ABSlotManager
from openrobo_agent.deployment.staging import stage_release_artifact
from openrobo_agent.deployment.worker import (
    DeploymentWorker,
    GenerationStateCorruptedError,
    GenerationStateManager,
    PersistedGenerationState,
)

__all__ = [
    "ABSlotManager",
    "ActivationIntent",
    "SlotMetadata",
    "SlotState",
    "SlotsState",
    "activate_staged_slot",
    "rollback_to_previous",
    "stage_release_artifact",
    "ArtifactClient",
    "SSRFValidationError",
    "ArtifactVerificationError",
    "DeploymentWorker",
    "GenerationStateManager",
    "PersistedGenerationState",
    "GenerationStateCorruptedError",
]
