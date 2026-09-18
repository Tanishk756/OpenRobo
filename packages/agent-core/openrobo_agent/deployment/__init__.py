"""OpenRobo Agent Local Deployment Subsystem."""

from openrobo_agent.deployment.activation import activate_staged_slot
from openrobo_agent.deployment.models import SlotMetadata, SlotState
from openrobo_agent.deployment.rollback import rollback_to_previous
from openrobo_agent.deployment.slots import ABSlotManager
from openrobo_agent.deployment.staging import stage_release_artifact

__all__ = [
    "SlotMetadata",
    "SlotState",
    "ABSlotManager",
    "stage_release_artifact",
    "activate_staged_slot",
    "rollback_to_previous",
]
