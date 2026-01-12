"""
Specialized modules for the assistant orchestrator

Each module provides specific capabilities and is stateless.
The orchestrator manages context and routes work to modules.
"""
from .base import BaseModule
from .follow_up import FollowUpModule
from .communication import CommunicationModule
from .scheduling import SchedulingModule

__all__ = [
    "BaseModule",
    "FollowUpModule",
    "CommunicationModule",
    "SchedulingModule",
]
