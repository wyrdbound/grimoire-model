"""
Primitive type registry for managing custom primitive types.

This module provides a registry for custom primitive types that should be
treated as primitive values rather than complex model objects.
"""

from __future__ import annotations

import threading
from typing import Callable

from ..logging import get_logger

logger = get_logger("core.primitive_registry")


class PrimitiveTypeRegistry:
    """Registry for custom primitive types.

    This registry allows users to register domain-specific primitive types
    (e.g., 'roll' for dice notation, 'duration' for time periods) that should
    be treated as primitive values like str or int, rather than as custom
    model types requiring model registration and resolution.

    Example:
        registry = PrimitiveTypeRegistry()
        registry.register('roll', validator=validate_dice_roll)
        registry.is_registered('roll')  # Returns True
        registry.is_registered('custom_model')  # Returns False
    """

    def __init__(self):
        """Initialize the PrimitiveTypeRegistry."""
        self._primitives: dict[str, Callable | None] = {}
        self._lock = threading.RLock()

    def register(self, type_name: str, validator: Callable | None = None) -> None:
        """Register a custom primitive type.

        Args:
            type_name: The name of the primitive type (e.g., 'roll', 'duration')
            validator: Optional validation function for the primitive type.
                      Should accept a value and return (is_valid, error_message).

        Raises:
            ValueError: If the type_name is empty or a built-in primitive
        """
        if not type_name or not isinstance(type_name, str):
            raise ValueError("type_name must be a non-empty string")

        # Prevent overriding built-in primitives
        builtin_primitives = {"int", "str", "float", "bool", "list", "dict"}
        if type_name.lower() in builtin_primitives:
            raise ValueError(
                f"Cannot register '{type_name}' as it is a built-in primitive type"
            )

        with self._lock:
            if type_name in self._primitives:
                logger.warning(
                    f"Primitive type '{type_name}' is already registered. "
                    "Overwriting with new validator."
                )
            self._primitives[type_name] = validator
            logger.debug(f"Registered primitive type: {type_name}")

    def unregister(self, type_name: str) -> bool:
        """Unregister a custom primitive type.

        Args:
            type_name: The name of the primitive type to unregister

        Returns:
            True if the type was unregistered, False if it wasn't registered
        """
        with self._lock:
            if type_name in self._primitives:
                del self._primitives[type_name]
                logger.debug(f"Unregistered primitive type: {type_name}")
                return True
            return False

    def is_registered(self, type_name: str) -> bool:
        """Check if a type is registered as a primitive.

        Args:
            type_name: The type name to check

        Returns:
            True if the type is registered as a custom primitive
        """
        with self._lock:
            return type_name in self._primitives

    def get_validator(self, type_name: str) -> Callable | None:
        """Get the validator for a registered primitive type.

        Args:
            type_name: The name of the primitive type

        Returns:
            The validator function if registered, None otherwise
        """
        with self._lock:
            return self._primitives.get(type_name)

    def list_registered_types(self) -> list[str]:
        """Get a list of all registered custom primitive types.

        Returns:
            List of registered primitive type names
        """
        with self._lock:
            return list(self._primitives.keys())

    def clear(self) -> int:
        """Clear all registered primitive types.

        Returns:
            Number of types removed
        """
        with self._lock:
            count = len(self._primitives)
            self._primitives.clear()
            logger.debug(f"Cleared {count} primitive types from registry")
            return count

    def __len__(self) -> int:
        """Return the number of registered primitive types."""
        with self._lock:
            return len(self._primitives)

    def __contains__(self, type_name: str) -> bool:
        """Check if a type is registered using 'in' operator."""
        return self.is_registered(type_name)

    def __repr__(self) -> str:
        """String representation of the registry."""
        with self._lock:
            return (
                f"PrimitiveTypeRegistry({len(self._primitives)} types: "
                f"{list(self._primitives.keys())})"
            )


# Global primitive type registry instance
_default_primitive_registry: PrimitiveTypeRegistry | None = None
_primitive_registry_lock = threading.RLock()


def get_default_primitive_registry() -> PrimitiveTypeRegistry:
    """Get the default primitive type registry, creating it if needed.

    This function is thread-safe and uses lazy initialization.

    Returns:
        The default PrimitiveTypeRegistry instance
    """
    global _default_primitive_registry
    if _default_primitive_registry is None:
        with _primitive_registry_lock:
            # Double-checked locking pattern
            if _default_primitive_registry is None:
                _default_primitive_registry = PrimitiveTypeRegistry()
    return _default_primitive_registry


def register_primitive_type(
    type_name: str,
    validator: Callable | None = None,
    registry: PrimitiveTypeRegistry | None = None,
) -> None:
    """Register a custom primitive type in the registry.

    This is the main API for registering domain-specific primitive types
    that should be treated as primitive values rather than custom models.

    Args:
        type_name: The name of the primitive type (e.g., 'roll', 'duration')
        validator: Optional validation function for the primitive type
        registry: Optional registry to use. If None, uses default registry.

    Example:
        # Register a dice roll type
        register_primitive_type('roll')

        # Register with validation
        def validate_duration(value):
            # Return (is_valid, error_message)
            if isinstance(value, str) and value.endswith('s'):
                return True, None
            return False, "Duration must end with 's'"

        register_primitive_type('duration', validator=validate_duration)
    """
    if registry is None:
        registry = get_default_primitive_registry()
    registry.register(type_name, validator)


def unregister_primitive_type(
    type_name: str,
    registry: PrimitiveTypeRegistry | None = None,
) -> bool:
    """Unregister a custom primitive type.

    Args:
        type_name: The name of the primitive type to unregister
        registry: Optional registry to use. If None, uses default registry.

    Returns:
        True if the type was unregistered, False if it wasn't registered
    """
    if registry is None:
        registry = get_default_primitive_registry()
    return registry.unregister(type_name)


def is_primitive_type(
    type_name: str,
    registry: PrimitiveTypeRegistry | None = None,
) -> bool:
    """Check if a type is registered as a custom primitive.

    Args:
        type_name: The type name to check
        registry: Optional registry to use. If None, uses default registry.

    Returns:
        True if the type is registered as a custom primitive
    """
    if registry is None:
        registry = get_default_primitive_registry()
    return registry.is_registered(type_name)


def clear_primitive_registry(
    registry: PrimitiveTypeRegistry | None = None,
) -> int:
    """Clear all custom primitive types from the registry.

    This is primarily useful for testing.

    Args:
        registry: Optional registry to clear. If None, uses default registry.

    Returns:
        Number of types removed
    """
    if registry is None:
        registry = get_default_primitive_registry()
    return registry.clear()
