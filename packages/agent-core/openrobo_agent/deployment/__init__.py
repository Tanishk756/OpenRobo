"""Local A/B workspace slot manager, staging, atomic activation, and rollback subsystem."""

from openrobo_agent.deployment.activation import activate_staged_slot
from openrobo_agent.deployment.models import ActivationIntent, SlotMetadata, SlotsState, SlotState
from openrobo_agent.deployment.rollback import rollback_to_previous
from openrobo_agent.deployment.slots import ABSlotManager
from openrobo_agent.deployment.staging import stage_release_artifact

__all__ = [
    "ABSlotManager",
    "ActivationIntent",
    "SlotMetadata",
    "SlotState",
    "SlotsState",
    "activate_staged_slot",
    "rollback_to_previous",
    "stage_release_artifact",
]
