class ProjectError(Exception):
    """Base exception for the project."""


class ConfigurationError(ProjectError):
    """Raised when required configuration is missing or invalid."""


class ExternalDependencyError(ProjectError):
    """Raised when an external command or service dependency is unavailable."""

