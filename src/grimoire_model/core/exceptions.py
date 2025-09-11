"""
Core exceptions for grimoire-model package.

Provides a hierarchy of exceptions for different error conditions that can occur
during model operations, validation, template resolution, and inheritance processing.
"""

from typing import Any, Dict, List, Optional


class GrimoireModelError(Exception):
    """Base exception for grimoire-model package.

    All other exceptions in this package inherit from this base class.
    """

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Initialize with message and optional context information.

        Args:
            message: Human-readable error description
            context: Additional context information for debugging
        """
        super().__init__(message)
        self.message = message
        self.context = context or {}

    def __str__(self) -> str:
        """Return string representation with context if available."""
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} (context: {context_str})"
        return self.message


class ModelValidationError(GrimoireModelError):
    """Raised when model validation fails.

    This exception is raised when:
    - Required fields are missing
    - Field values don't match their defined types
    - Value constraints are violated (range, enum, etc.)
    - Cross-field validation rules fail
    """

    def __init__(
        self,
        message: str,
        field_name: Optional[str] = None,
        field_value: Any = None,
        validation_errors: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Initialize validation error with field-specific information.

        Args:
            message: Primary error message
            field_name: Name of the field that failed validation
            field_value: Value that caused the validation failure
            validation_errors: List of specific validation error messages
            context: Additional context information
        """
        super().__init__(message, context)
        self.field_name = field_name
        self.field_value = field_value
        self.validation_errors = validation_errors or []

    def __str__(self) -> str:
        """Return detailed string representation including field information."""
        parts = [self.message]

        if self.field_name:
            parts.append(f"field: {self.field_name}")

        if self.field_value is not None:
            parts.append(f"value: {self.field_value}")

        if self.validation_errors:
            error_list = ", ".join(self.validation_errors)
            parts.append(f"errors: [{error_list}]")

        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            parts.append(f"context: {context_str}")

        return " | ".join(parts)


class TemplateResolutionError(GrimoireModelError):
    """Raised when template resolution fails.

    This exception is raised when:
    - Template syntax is invalid
    - Referenced variables are undefined
    - Template evaluation produces an error
    - Circular template dependencies are detected
    """

    def __init__(
        self,
        message: str,
        template_str: Optional[str] = None,
        template_variables: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Initialize template resolution error.

        Args:
            message: Primary error message
            template_str: The template string that failed to resolve
            template_variables: Variables referenced in the template
            context: Additional context information
        """
        super().__init__(message, context)
        self.template_str = template_str
        self.template_variables = template_variables or []

    def __str__(self) -> str:
        """Return detailed string representation including template information."""
        parts = [self.message]

        if self.template_str:
            parts.append(f"template: {self.template_str}")

        if self.template_variables:
            vars_str = ", ".join(self.template_variables)
            parts.append(f"variables: [{vars_str}]")

        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            parts.append(f"context: {context_str}")

        return " | ".join(parts)


class InheritanceError(GrimoireModelError):
    """Raised when model inheritance resolution fails.

    This exception is raised when:
    - Parent model definitions are not found
    - Circular inheritance dependencies are detected
    - Inheritance conflicts cannot be resolved
    - Model registry is incomplete or corrupted
    """

    def __init__(
        self,
        message: str,
        model_id: Optional[str] = None,
        parent_ids: Optional[List[str]] = None,
        inheritance_chain: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Initialize inheritance error.

        Args:
            message: Primary error message
            model_id: ID of the model that failed inheritance resolution
            parent_ids: List of parent model IDs
            inheritance_chain: The inheritance chain being resolved
            context: Additional context information
        """
        super().__init__(message, context)
        self.model_id = model_id
        self.parent_ids = parent_ids or []
        self.inheritance_chain = inheritance_chain or []

    def __str__(self) -> str:
        """Return detailed string representation including inheritance information."""
        parts = [self.message]

        if self.model_id:
            parts.append(f"model: {self.model_id}")

        if self.parent_ids:
            parents_str = ", ".join(self.parent_ids)
            parts.append(f"parents: [{parents_str}]")

        if self.inheritance_chain:
            chain_str = " -> ".join(self.inheritance_chain)
            parts.append(f"chain: {chain_str}")

        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            parts.append(f"context: {context_str}")

        return " | ".join(parts)


class DependencyError(GrimoireModelError):
    """Raised when derived field dependencies cannot be resolved.

    This exception is raised when:
    - Circular dependencies are detected between derived fields
    - Required dependencies are missing or undefined
    - Dependency graph cannot be topologically sorted
    - Dependency computation fails
    """

    def __init__(
        self,
        message: str,
        field_name: Optional[str] = None,
        dependencies: Optional[List[str]] = None,
        dependency_chain: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Initialize dependency error.

        Args:
            message: Primary error message
            field_name: Name of the field with dependency issues
            dependencies: List of field dependencies
            dependency_chain: The dependency chain that failed
            context: Additional context information
        """
        super().__init__(message, context)
        self.field_name = field_name
        self.dependencies = dependencies or []
        self.dependency_chain = dependency_chain or []

    def __str__(self) -> str:
        """Return detailed string representation including dependency information."""
        parts = [self.message]

        if self.field_name:
            parts.append(f"field: {self.field_name}")

        if self.dependencies:
            deps_str = ", ".join(self.dependencies)
            parts.append(f"deps: [{deps_str}]")

        if self.dependency_chain:
            chain_str = " -> ".join(self.dependency_chain)
            parts.append(f"chain: {chain_str}")

        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            parts.append(f"context: {context_str}")

        return " | ".join(parts)


class ConfigurationError(GrimoireModelError):
    """Raised when configuration is invalid or incomplete.

    This exception is raised when:
    - Required configuration parameters are missing
    - Configuration values are invalid
    - Dependency injection setup fails
    - Resolver configuration is incomplete
    """

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        config_value: Any = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Initialize configuration error.

        Args:
            message: Primary error message
            config_key: Configuration key that caused the error
            config_value: Invalid configuration value
            context: Additional context information
        """
        super().__init__(message, context)
        self.config_key = config_key
        self.config_value = config_value

    def __str__(self) -> str:
        """Return detailed string representation including configuration information."""
        parts = [self.message]

        if self.config_key:
            parts.append(f"key: {self.config_key}")

        if self.config_value is not None:
            parts.append(f"value: {self.config_value}")

        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            parts.append(f"context: {context_str}")

        return " | ".join(parts)
