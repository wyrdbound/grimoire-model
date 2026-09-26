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


def _resolve_parent(
    parent_id: str,
    namespace: str,
    model_registry: Union[dict[str, ModelDefinition], ModelRegistry],
) -> ModelDefinition | None:
    """Resolve a parent, namespace-local when the registry supports it (R41).

    A plain id-keyed dict has no namespace, so this falls back to
    :func:`_find_model_in_registry` (rule 6).
    """
    if hasattr(model_registry, "lookup"):
        try:
            return model_registry.lookup(parent_id, namespace)  # type: ignore[union-attr]
        except KeyError:
            return None
    return _find_model_in_registry(parent_id, _normalize_registry(model_registry))


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

    Per the specification (`model_spec.md`, Inheritance Rules 4): "Later models
    override fields from earlier ones." resolved(M) = merge of resolved(P1) …
    resolved(Pn) in ``extends`` order, then M's own attributes; each later
    source replaces an earlier attribute of the same name (R40, D11).
    Validations accumulate in the same order, de-duplicated by (expression,
    message).

    Args:
        model_def: The model definition to resolve inheritance for
        model_registry: Registry of all available model definitions (dict or
            ModelRegistry)
        max_depth: Maximum inheritance depth (the longest ``extends`` path)

    Returns:
        New ModelDefinition with resolved inheritance. The result is not
        registered.

    Raises:
        InheritanceError: If inheritance cannot be resolved
    """
    if not model_def.has_inheritance():
        return model_def

    logger.debug(f"Resolving inheritance for model '{model_def.id}'")

    resolved_attributes, resolved_validations = _resolve_sources(
        model_def, model_registry, max_depth
    )

    resolved_model = ModelDefinition(
        id=model_def.id,
        name=model_def.name,
        kind=model_def.kind,
        description=model_def.description,
        version=model_def.version,
        extends=[],  # Clear extends since we've resolved inheritance
        attributes=resolved_attributes,
        validations=resolved_validations,
        tags=model_def.tags.copy(),
        metadata=model_def.metadata.copy(),
    )

    logger.debug(
        f"Resolved model '{model_def.id}' with {len(resolved_attributes)} attributes"
    )
    return resolved_model


def _resolve_sources(
    model_def: ModelDefinition,
    model_registry: Union[dict[str, ModelDefinition], ModelRegistry],
    max_depth: int,
) -> tuple[dict[str, AttributeDefinition], list[ValidationRule]]:
    """Merge a model's own and its ancestors' attributes and validations.

    resolved(M) = merge(resolved(P1) … resolved(Pn), own(M)) in ``extends``
    order: each parent's fully resolved sources first, then M's own, each later
    source replacing an earlier attribute of the same name (R40, D11). Each
    ancestor is resolved once (a diamond does not double-merge a shared base).
    ``max_depth`` bounds the longest ``extends`` path from M (R43), and any
    cycle reachable from M raises ``InheritanceError`` naming the cycle (R44).
    """
    cache: dict[tuple[str, str], tuple[dict[str, AttributeDefinition], list]] = {}
    path: list[tuple[str, str]] = []

    def _resolve(
        current: ModelDefinition, depth: int
    ) -> tuple[dict[str, AttributeDefinition], list[ValidationRule]]:
        key = (current.namespace, current.id)
        if key in cache:
            return cache[key]

        if key in path:
            cycle = [model_id for _, model_id in path[path.index(key) :]] + [current.id]
            raise InheritanceError(
                f"Circular inheritance detected: {' -> '.join(cycle)}",
                model_id=model_def.id,
                inheritance_chain=cycle,
            )
        if depth > max_depth:
            raise InheritanceError(
                f"Maximum inheritance depth ({max_depth}) exceeded",
                model_id=model_def.id,
                inheritance_chain=[model_id for _, model_id in path] + [current.id],
            )

        path.append(key)
        try:
            attributes: dict[str, AttributeDefinition] = {}
            validations: list[ValidationRule] = []
            seen_rules: set[tuple[str, str]] = set()

            for parent_id in current.extends:
                parent = _resolve_parent(parent_id, current.namespace, model_registry)
                if parent is None:
                    raise InheritanceError(
                        f"Parent model '{parent_id}' not found in namespace "
                        f"'{current.namespace}' or uniquely elsewhere",
                        model_id=current.id,
                        parent_ids=[parent_id],
                    )
                parent_attrs, parent_rules = _resolve(parent, depth + 1)
                attributes.update(parent_attrs)
                for rule in parent_rules:
                    rule_key = (rule.expression, rule.message)
                    if rule_key not in seen_rules:
                        validations.append(rule)
                        seen_rules.add(rule_key)

            for attr_name, attr_def in current.attributes.items():
                if isinstance(attr_def, AttributeDefinition):
                    attributes[attr_name] = attr_def
                else:
                    attributes[attr_name] = AttributeDefinition(**attr_def)
            for rule in current.validations:
                rule_key = (rule.expression, rule.message)
                if rule_key not in seen_rules:
                    validations.append(rule)
                    seen_rules.add(rule_key)

            result = (attributes, validations)
            cache[key] = result
            return result
        finally:
            path.pop()

    return _resolve(model_def, 0)


def _get_inheritance_chain(
    model_def: ModelDefinition,
    model_registry: dict[str, ModelDefinition],
    max_depth: int,
) -> list[str]:
    """Get the set of model IDs reachable from a model via ``extends``.

    A breadth-first walk over the ``extends`` graph. Used by the registry
    analysis helpers, not by :func:`resolve_model_inheritance`, which resolves
    recursively in ``extends`` order.

    Args:
        model_def: The model definition to get the chain for
        model_registry: Registry of all available model definitions
        max_depth: Maximum number of nodes to visit

    Returns:
        List of model IDs reachable from the model (including itself)

    Raises:
        InheritanceError: If a parent is missing or a cycle reaches the model
    """
    # Start with the model itself
    chain = [model_def.id]
    visited = {model_def.id}
    depth = 0

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

            # Queue parent's parents for processing
            if parent_model.extends:
                queue.append((parent_id, parent_model.extends))

    if depth >= max_depth:
        raise InheritanceError(
            f"Maximum inheritance depth ({max_depth}) exceeded",
            model_id=model_def.id,
            inheritance_chain=chain,
        )

    return chain


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
