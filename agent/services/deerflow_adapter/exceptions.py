"""DeerFlow adapter exceptions."""


class DeerFlowError(Exception):
    """Base exception for DeerFlow adapter errors."""
    pass


class DeerFlowTimeoutError(DeerFlowError):
    """DeerFlow call exceeded the configured timeout."""
    pass


class DeerFlowSkillNotFoundError(DeerFlowError):
    """Requested skill is not registered in DeerFlow."""
    pass
