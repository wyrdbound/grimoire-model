"""
Model registry for managing ModelDefinition instances.
"""

from __future__ import annotations

import threading

from ..logging import get_logger
from .schema import ModelDefinition

logger = get_logger("core.registry")


class ModelRegistry:
    """Global registry for ModelDefinitions with namespace support.

    The registry uses namespaced keys in the format "namespace__model_id" to
    organize models and prevent naming conflicts across different domains.

    Example:
        registry = ModelRegistry()
        registry.register("game", "character", character_def)
        registry.get("game", "character")  # Returns character_def
        registry.get_by_key("game__character")  # Same result
    """

    def __init__(self):
        """Initialize the ModelRegistry."""
        self._models: dict[str, ModelDefinition] = {}
        self._lock = threading.RLock()
        self._namespaces: set[str] = set()

    def register(
        self, namespace: str, model_id: str, model_definition: ModelDefinition
    ) -> None:
        """Register a model definition in the given namespace.

        Args:
            namespace: The namespace for the model (e.g., "game", "system", "custom")
            model_id: The unique ID of the model within the namespace
            model_definition: The ModelDefinition instance to register

        Raises:
            ValueError: If the namespaced key already exists with a different definition
        """
        key = f"{namespace}__{model_id}"

        with self._lock:
            if key in self._models:
                existing = self._models[key]
                if existing is not model_definition:
                    logger.warning(
                        f"Model '{key}' already registered. "
                        f"Overwriting with new definition."
                    )

            self._models[key] = model_definition
            self._namespaces.add(namespace)

        logger.debug(f"Registered model '{model_id}' in namespace '{namespace}'")

    def get(self, namespace: str, model_id: str) -> ModelDefinition | None:
        """Get a model definition by namespace and ID.

        Args:
            namespace: The namespace to search in
            model_id: The model ID to find

        Returns:
            The ModelDefinition if found, None otherwise
        """
        key = f"{namespace}__{model_id}"
        return self.get_by_key(key)

    def get_by_key(self, key: str) -> ModelDefinition | None:
        """Get a model definition by its full namespaced key.

        Args:
            key: The full key in format "namespace__model_id"

        Returns:
            The ModelDefinition if found, None otherwise
        """
        with self._lock:
            return self._models.get(key)

    def has(self, namespace: str, model_id: str) -> bool:
        """Check if a model exists in the registry.

        Args:
            namespace: The namespace to search in
            model_id: The model ID to check

        Returns:
            True if the model exists, False otherwise
        """
        key = f"{namespace}__{model_id}"
        return self.has_key(key)

    def has_key(self, key: str) -> bool:
        """Check if a namespaced key exists in the registry.

        Args:
            key: The full key in format "namespace__model_id"

        Returns:
            True if the key exists, False otherwise
        """
        with self._lock:
            return key in self._models

    def unregister(self, namespace: str, model_id: str) -> bool:
        """Remove a model definition from the registry.

        Args:
            namespace: The namespace of the model
            model_id: The model ID to remove

        Returns:
            True if the model was removed, False if it didn't exist
        """
        key = f"{namespace}__{model_id}"
        return self.unregister_by_key(key)

    def unregister_by_key(self, key: str) -> bool:
        """Remove a model definition by its full namespaced key.

        Args:
            key: The full key in format "namespace__model_id"

        Returns:
            True if the model was removed, False if it didn't exist
        """
        with self._lock:
            if key in self._models:
                del self._models[key]
                logger.debug(f"Unregistered model '{key}'")
                return True
            return False

    def list_models(self, namespace: str | None = None) -> list[str]:
        """List all model keys, optionally filtered by namespace.

        Args:
            namespace: If provided, only return models from this namespace

        Returns:
            List of model keys (full namespaced keys)
        """
        with self._lock:
            if namespace is None:
                return list(self._models.keys())

            prefix = f"{namespace}__"
            return [key for key in self._models.keys() if key.startswith(prefix)]

    def list_namespaces(self) -> list[str]:
        """List all registered namespaces.

        Returns:
            List of namespace names
        """
        with self._lock:
            return sorted(self._namespaces)

    def clear_namespace(self, namespace: str) -> int:
        """Remove all models from a specific namespace.

        Args:
            namespace: The namespace to clear

        Returns:
            Number of models removed
        """
        with self._lock:
            prefix = f"{namespace}__"
            keys_to_remove = [
                key for key in self._models.keys() if key.startswith(prefix)
            ]

            for key in keys_to_remove:
                del self._models[key]

            if namespace in self._namespaces and not any(
                key.startswith(prefix) for key in self._models.keys()
            ):
                self._namespaces.remove(namespace)

            logger.debug(
                f"Cleared {len(keys_to_remove)} models from namespace '{namespace}'"
            )
            return len(keys_to_remove)

    def clear_all(self) -> int:
        """Remove all models from the registry.

        Returns:
            Number of models removed
        """
        with self._lock:
            count = len(self._models)
            self._models.clear()
            self._namespaces.clear()
            logger.debug(f"Cleared all {count} models from registry")
            return count

    def get_registry_dict(
        self, namespace: str | None = None
    ) -> dict[str, ModelDefinition]:
        """Get a dictionary representation of the registry.

        Args:
            namespace: If provided, only return models from this namespace

        Returns:
            Dictionary mapping full keys to ModelDefinitions
        """
        with self._lock:
            if namespace is None:
                return dict(self._models)

            prefix = f"{namespace}__"
            return {
                key: model_def
                for key, model_def in self._models.items()
                if key.startswith(prefix)
            }

    def resolve_extends(
        self, namespace: str, extends: list[str]
    ) -> list[ModelDefinition]:
        """Resolve a list of parent model IDs to ModelDefinitions.

        This method looks up parent models first in the same namespace, then in
        other namespaces if not found.

        Args:
            namespace: The namespace of the child model
            extends: List of parent model IDs to resolve

        Returns:
            List of resolved ModelDefinitions

        Raises:
            KeyError: If any parent model cannot be found
        """
        resolved = []

        with self._lock:
            for parent_id in extends:
                # First try in the same namespace
                parent_def = self.get(namespace, parent_id)

                if parent_def is None:
                    # Search across all namespaces
                    found = False
                    for key, model_def in self._models.items():
                        if key.endswith(f"__{parent_id}"):
                            parent_def = model_def
                            found = True
                            logger.debug(
                                f"Found parent '{parent_id}' in different "
                                f"namespace: {key}"
                            )
                            break

                    if not found:
                        raise KeyError(
                            f"Parent model '{parent_id}' not found in "
                            f"namespace '{namespace}' or any other namespace"
                        )

                # At this point parent_def is guaranteed to be not None
                assert parent_def is not None
                resolved.append(parent_def)

        return resolved

    def __len__(self) -> int:
        """Return the total number of registered models."""
        with self._lock:
            return len(self._models)

    def __contains__(self, key: str) -> bool:
        """Check if a key exists using 'in' operator."""
        return self.has_key(key)

    def __repr__(self) -> str:
        """String representation of the registry."""
        with self._lock:
            return (
                f"ModelRegistry({len(self._models)} models, "
                f"{len(self._namespaces)} namespaces)"
            )


# Private module-level registry with thread-safe lazy initialization
_registry_lock = threading.Lock()
_default_registry: ModelRegistry | None = None


def get_default_registry() -> ModelRegistry:
    """Get the default model registry, creating it if needed.

    This function is thread-safe and uses lazy initialization.

    Returns:
        The default ModelRegistry instance
    """
    global _default_registry
    if _default_registry is None:
        with _registry_lock:
            # Double-checked locking pattern
            if _default_registry is None:
                _default_registry = ModelRegistry()
    return _default_registry


def get_model_registry() -> ModelRegistry:
    """Get the global model registry instance.

    Returns:
        The default ModelRegistry instance

    Deprecated:
        Use get_default_registry() instead for clearer semantics
    """
    return get_default_registry()


def clear_registry(registry: ModelRegistry | None = None) -> int:
    """Clear all models from the registry.

    This is primarily useful for testing.

    Args:
        registry: Optional registry to clear. If None, uses default registry.

    Returns:
        Number of models removed
    """
    if registry is None:
        registry = get_default_registry()
    return registry.clear_all()


def register_model(
    namespace: str,
    model_definition: ModelDefinition,
    registry: ModelRegistry | None = None,
) -> None:
    """Register a model definition in the registry.

    Args:
        namespace: The namespace for the model
        model_definition: The ModelDefinition to register
        registry: Optional registry to use. If None, uses default registry.
    """
    if registry is None:
        registry = get_default_registry()
    registry.register(namespace, model_definition.id, model_definition)


def get_model(
    namespace: str, model_id: str, registry: ModelRegistry | None = None
) -> ModelDefinition | None:
    """Get a model from the registry.

    Args:
        namespace: The namespace to search in
        model_id: The model ID to find
        registry: Optional registry to use. If None, uses default registry.

    Returns:
        The ModelDefinition if found, None otherwise
    """
    if registry is None:
        registry = get_default_registry()
    return registry.get(namespace, model_id)
