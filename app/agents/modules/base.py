"""
Base module class for all assistant modules

Modules are specialized, stateless capabilities that:
- Return results, not decisions
- Are reusable across workflows
- Can be combined by the orchestrator
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime


class BaseModule(ABC):
    """
    Base class for all assistant modules

    Modules should be stateless and focused on specific capabilities.
    The orchestrator manages state and decision-making.
    """

    def __init__(self):
        """Initialize the module"""
        self.module_name = self.__class__.__name__

    @abstractmethod
    def get_capabilities(self) -> Dict[str, str]:
        """
        Return a dictionary of capabilities this module provides

        Returns:
            Dict mapping capability name to description

        Example:
            {
                "generate_reply": "Generate a reply draft for a message",
                "check_sentiment": "Analyze message sentiment"
            }
        """
        pass

    def validate_input(self, **kwargs) -> bool:
        """
        Validate input parameters before execution

        Override this in subclasses to add specific validation.

        Returns:
            True if valid, False otherwise
        """
        return True

    def log_execution(
        self,
        capability: str,
        input_data: Dict[str, Any],
        result: Any,
        success: bool = True,
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a log entry for module execution

        Args:
            capability: Which capability was executed
            input_data: Input parameters
            result: Result returned
            success: Whether execution succeeded
            error: Error message if failed

        Returns:
            Log entry dictionary
        """
        return {
            "module": self.module_name,
            "capability": capability,
            "timestamp": datetime.utcnow().isoformat(),
            "input": input_data,
            "result": result,
            "success": success,
            "error": error
        }

    def execute(self, capability: str, **kwargs) -> Dict[str, Any]:
        """
        Execute a specific capability

        This is a convenience method that routes to the appropriate method.
        Override in subclasses if needed.

        Args:
            capability: Name of the capability to execute
            **kwargs: Parameters for the capability

        Returns:
            Result dictionary with "success", "data", and optional "error" keys
        """
        if not self.validate_input(**kwargs):
            return {
                "success": False,
                "error": "Invalid input parameters",
                "data": None
            }

        # Check if capability exists as a method
        if not hasattr(self, capability):
            return {
                "success": False,
                "error": f"Capability '{capability}' not found in {self.module_name}",
                "data": None
            }

        try:
            method = getattr(self, capability)
            result = method(**kwargs)

            return {
                "success": True,
                "data": result,
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "data": None
            }
