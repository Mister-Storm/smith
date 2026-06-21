class SmithError(Exception):
    """Base exception for Smith."""


class ConfigurationError(SmithError):
    """Raised when configuration is invalid or incomplete."""


class ToolExecutionError(SmithError):
    """Raised when a tool fails to execute."""


class GitNotRepositoryError(SmithError):
    """Raised when the current directory is not a Git repository."""


class WorkspaceNoProjectsError(SmithError):
    """Raised when workspace discovery finds no projects."""


INVESTIGATION_FAILURE_MESSAGE = "Repository investigation failed unexpectedly."


class InvestigationFailure(SmithError):
    """Raised when a resolved repository produces zero evidence items."""
