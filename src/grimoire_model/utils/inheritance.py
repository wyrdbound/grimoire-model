"""
Model inheritance resolution for grimoire-model package.

Provides functions for resolving model inheritance chains, handling multiple
inheritance, and merging attribute definitions from parent models.
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Union

from ..core.exceptions import InheritanceError
from ..core.schema import AttributeDefinition, ModelDefinition, ValidationRule
from ..logging import get_logger

if TYPE_CHECKING:
    from ..core.registry import ModelRegistry

logger = get_logger("utils.inheritance")


def _normalize_registry(
    model_registry: Union[dict[str, ModelDefinition], ModelRegistry],
) -> dict[str, ModelDefinition]:
    """Normalize a model registry to dict format.

    Args:
        model_registry: Registry in dict or ModelRegistry format

    Returns:
        Registry as a dictionary
    """
    if hasattr(model_registry, "get_registry_dict") and callable(
        model_registry.get_registry_dict
    ):
        # It's a ModelRegistry instance
        return model_registry.get_registry_dict()  # type: ignore
    else:
        # It's already a dict
        return model_registry  # type: ignore


def _find_model_in_registry(
    model_id: str, model_registry: dict[str, ModelDefinition]
) -> ModelDefinition | None:
    """Find a model in the registry by ID, handling both direct and namespaced keys.

    Args:
        model_id: The model ID to find
        model_registry: Registry of models

    Returns:
        The ModelDefinition if found, None otherwise
    """
    # First check if it's a direct match (backward compatibility)
    if model_id in model_registry:
        return model_registry[model_id]

    # Search for namespaced keys ending with the model_id
    for key, model in model_registry.items():
        if key.endswith(f"__{model_id}"):
            return model

    return None


def resolve_model_inheritance(
    model_def: ModelDefinition,
    model_registry: Union[dict[str, ModelDefinition], ModelRegistry],
    max_depth: int = 10,
) -> ModelDefinition:
    """Resolve inheritance for a model definition.

    Args:
        model_def: The model definition to resolve inheritance for
        model_registry: Registry of all available model definitions (dict or
            ModelRegistry)
        max_depth: Maximum inheritance depth to prevent infinite recursion

    Returns:
        New ModelDefinition with resolved inheritance

    Raises:
        InheritanceError: If inheritance cannot be resolved
    """
    if not model_def.has_inheritance():
        return model_def

    logger.debug(f"Resolving inheritance for model '{model_def.id}'")

    # Normalize registry to dict format for backward compatibility
    registry_dict = _normalize_registry(model_registry)

    # Get inheritance chain
    inheritance_chain = _get_inheritance_chain(model_def, registry_dict, max_depth)
    logger.debug(f"Inheritance chain for '{model_def.id}': {inheritance_chain}")

    # Resolve attributes from inheritance chain
    resolved_attributes = _resolve_attributes(inheritance_chain, registry_dict)

    # Resolve validation rules
    resolved_validations = _resolve_validations(inheritance_chain, registry_dict)

    # Create resolved model definition
    # Use resolved_attributes directly since it contains AttributeDefinition objects
    attributes_union: dict[str, AttributeDefinition] = resolved_attributes

    resolved_model = ModelDefinition(
        id=model_def.id,
        name=model_def.name,
        kind=model_def.kind,
        description=model_def.description,
        version=model_def.version,
        extends=[],  # Clear extends since we've resolved inheritance
        attributes=attributes_union,
        validations=resolved_validations,
        tags=model_def.tags.copy(),
        metadata=model_def.metadata.copy(),
    )

    logger.debug(
        f"Resolved model '{model_def.id}' with {len(resolved_attributes)} attributes"
    )
    return resolved_model


def _get_inheritance_chain(
    model_def: ModelDefinition,
    model_registry: dict[str, ModelDefinition],
    max_depth: int,
) -> list[str]:
    """Get the complete inheritance chain for a model using method resolution order.

    Uses C3 linearization algorithm for multiple inheritance resolution.

    Args:
        model_def: The model definition to get chain for
        model_registry: Registry of all available model definitions
        max_depth: Maximum inheritance depth

    Returns:
        List of model IDs in method resolution order (child to parent)

    Raises:
        InheritanceError: If inheritance chain cannot be resolved
    """
    # Start with the model itself
    chain = [model_def.id]
    visited = {model_def.id}
    depth = 0

    # Process inheritance using breadth-first search with C3 linearization
    queue = deque([(model_def.id, model_def.extends)])

    while queue and depth < max_depth:
        current_id, parent_ids = queue.popleft()
        depth += 1

        for parent_id in parent_ids:
            # Check if parent exists - handle both namespaced and non-namespaced keys
            parent_model = _find_model_in_registry(parent_id, model_registry)

            if parent_model is None:
                raise InheritanceError(
                    f"Parent model '{parent_id}' not found in registry",
                    model_id=current_id,
                    parent_ids=[parent_id],
                    inheritance_chain=chain,
                )

            # Check for circular inheritance
            if parent_id in visited:
                if parent_id == model_def.id:
                    raise InheritanceError(
                        f"Circular inheritance detected: model '{parent_id}' inherits "
                        f"from itself",
                        model_id=model_def.id,
                        parent_ids=parent_ids,
                        inheritance_chain=chain + [parent_id],
                    )
                continue  # Skip already processed parents

            # Add to chain and visited set
            chain.append(parent_id)
            visited.add(parent_id)

            # Queue parent's parents for processing (parent_model already resolved
            # above)
            if parent_model.extends:
                queue.append((parent_id, parent_model.extends))

    if depth >= max_depth:
        raise InheritanceError(
            f"Maximum inheritance depth ({max_depth}) exceeded",
            model_id=model_def.id,
            inheritance_chain=chain,
        )

    return chain


def _resolve_attributes(
    inheritance_chain: list[str], model_registry: dict[str, ModelDefinition]
) -> dict[str, AttributeDefinition]:
    """Resolve attributes from inheritance chain using method resolution order.

    Attributes are resolved in reverse inheritance order (parent to child),
    with child attributes overriding parent attributes.

    Args:
        inheritance_chain: List of model IDs in inheritance order
        model_registry: Registry of all available model definitions

    Returns:
        Dictionary of resolved attribute definitions
    """
    resolved_attributes = {}

    # Process inheritance chain in reverse order (parent to child)
    for model_id in reversed(inheritance_chain):
        model_def = _find_model_in_registry(model_id, model_registry)
        if model_def is None:
            raise InheritanceError(
                f"Model '{model_id}' not found in registry during attribute resolution",
                model_id=model_id,
            )

        for attr_name, attr_def in model_def.attributes.items():
            if isinstance(attr_def, AttributeDefinition):
                # Child attributes override parent attributes
                resolved_attributes[attr_name] = attr_def
                logger.debug(
                    f"Inherited attribute '{attr_name}' from model '{model_id}'"
                )
            else:
                # Convert dict to AttributeDefinition if needed
                resolved_attributes[attr_name] = AttributeDefinition(**attr_def)
                logger.debug(
                    f"Inherited and converted attribute '{attr_name}' from "
                    f"model '{model_id}'"
                )

    return resolved_attributes


def _resolve_validations(
    inheritance_chain: list[str], model_registry: dict[str, ModelDefinition]
) -> list[ValidationRule]:
    """Resolve validation rules from inheritance chain.

    Validation rules are accumulated from all models in the inheritance chain.

    Args:
        inheritance_chain: List of model IDs in inheritance order
        model_registry: Registry of all available model definitions

    Returns:
        List of all validation rules from the inheritance chain
    """
    resolved_validations = []
    seen_rules = set()  # Track unique rules to avoid duplicates

    # Process inheritance chain in reverse order (parent to child)
    for model_id in reversed(inheritance_chain):
        model_def = _find_model_in_registry(model_id, model_registry)
        if model_def is None:
            raise InheritanceError(
                f"Model '{model_id}' not found in registry during validation "
                f"resolution",
                model_id=model_id,
            )

        for validation in model_def.validations:
            # Create a unique key for the validation rule
            rule_key = (validation.expression, validation.message)

            if rule_key not in seen_rules:
                resolved_validations.append(validation)
                seen_rules.add(rule_key)
                logger.debug(
                    f"Inherited validation rule from model '{model_id}': "
                    f"{validation.expression}"
                )

    return resolved_validations


def check_inheritance_conflicts(
    model_def: ModelDefinition, model_registry: dict[str, ModelDefinition]
) -> list[str]:
    """Check for potential inheritance conflicts in a model definition.

    Args:
        model_def: The model definition to check
        model_registry: Registry of all available model definitions

    Returns:
        List of conflict descriptions (empty if no conflicts)
    """
    conflicts: list[str] = []

    if not model_def.has_inheritance():
        return conflicts

    try:
        inheritance_chain = _get_inheritance_chain(
            model_def, model_registry, max_depth=10
        )
    except InheritanceError as e:
        conflicts.append(str(e))
        return conflicts

    # Check for attribute type conflicts
    # attr_name -> [(model_id, attr_def), ...]
    attribute_sources: dict[str, list[tuple[str, AttributeDefinition]]] = {}

    for model_id in reversed(inheritance_chain):
        model = model_registry[model_id]

        for attr_name, attr_def in model.attributes.items():
            if attr_name not in attribute_sources:
                attribute_sources[attr_name] = []

            if isinstance(attr_def, AttributeDefinition):
                attribute_sources[attr_name].append((model_id, attr_def))
            else:
                # Convert dict to AttributeDefinition for comparison
                converted_attr = AttributeDefinition(**attr_def)
                attribute_sources[attr_name].append((model_id, converted_attr))

    # Check for type conflicts
    for attr_name, sources in attribute_sources.items():
        if len(sources) > 1:
            types = {attr_def.type for _, attr_def in sources}
            if len(types) > 1:
                type_info = ", ".join(
                    f"{model_id}: {attr_def.type}" for model_id, attr_def in sources
                )
                conflicts.append(
                    f"Attribute '{attr_name}' has conflicting types across "
                    f"inheritance chain: {type_info}"
                )

    return conflicts


def build_inheritance_graph(
    model_registry: dict[str, ModelDefinition],
) -> dict[str, set[str]]:
    """Build an inheritance graph from a model registry.

    Args:
        model_registry: Registry of all available model definitions

    Returns:
        Dictionary mapping model IDs to their direct children
    """
    inheritance_graph: dict[str, set[str]] = {
        model_id: set() for model_id in model_registry
    }

    for model_id, model_def in model_registry.items():
        for parent_id in model_def.extends:
            if parent_id in inheritance_graph:
                inheritance_graph[parent_id].add(model_id)

    return inheritance_graph


def find_inheritance_cycles(
    model_registry: dict[str, ModelDefinition],
) -> list[list[str]]:
    """Find all inheritance cycles in a model registry.

    Args:
        model_registry: Registry of all available model definitions

    Returns:
        List of cycles, where each cycle is a list of model IDs
    """
    cycles = []
    visited = set()
    rec_stack = set()

    def _dfs(model_id: str, path: list[str]) -> None:
        if model_id in rec_stack:
            # Found a cycle
            cycle_start = path.index(model_id)
            cycles.append(path[cycle_start:] + [model_id])
            return

        if model_id in visited:
            return

        visited.add(model_id)
        rec_stack.add(model_id)

        if model_id in model_registry:
            model_def = model_registry[model_id]
            for parent_id in model_def.extends:
                _dfs(parent_id, path + [model_id])

        rec_stack.remove(model_id)

    for model_id in model_registry:
        if model_id not in visited:
            _dfs(model_id, [])

    return cycles


def validate_model_registry(model_registry: dict[str, ModelDefinition]) -> list[str]:
    """Validate a model registry for inheritance issues.

    Args:
        model_registry: Registry of all available model definitions

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    # Check for inheritance cycles
    cycles = find_inheritance_cycles(model_registry)
    for cycle in cycles:
        cycle_str = " -> ".join(cycle)
        errors.append(f"Inheritance cycle detected: {cycle_str}")

    # Check for missing parent references
    for model_id, model_def in model_registry.items():
        for parent_id in model_def.extends:
            if parent_id not in model_registry:
                errors.append(f"Model '{model_id}' extends unknown model '{parent_id}'")

    # Check for individual model inheritance conflicts
    for model_id, model_def in model_registry.items():
        if model_def.has_inheritance():
            try:
                conflicts = check_inheritance_conflicts(model_def, model_registry)
                for conflict in conflicts:
                    errors.append(f"Model '{model_id}': {conflict}")
            except InheritanceError as e:
                errors.append(f"Model '{model_id}': {e}")

    return errors
