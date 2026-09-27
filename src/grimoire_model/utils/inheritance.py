"""
Model inheritance resolution for grimoire-model package.

Provides functions for resolving model inheritance chains, handling multiple
inheritance, and merging attribute definitions from parent models.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Union

from ..core.exceptions import InheritanceError
from ..core.schema import AttributeDefinition, ModelDefinition, ValidationRule
from ..logging import get_logger

if TYPE_CHECKING:
    from ..core.registry import ModelRegistry

logger = get_logger("utils.inheritance")


def _resolve_parent(
    parent_id: str,
    namespace: str,
    model_registry: Union[dict[str, ModelDefinition], ModelRegistry],
) -> ModelDefinition | None:
    """Resolve a parent namespace-locally, then uniquely (R41).

    A ``ModelRegistry`` uses its namespace-aware ``lookup``; a plain dict
    (rule 6) is re-keyed by each model's own namespace and matched the same
    way.
    """
    if hasattr(model_registry, "lookup"):
        try:
            return model_registry.lookup(parent_id, namespace)  # type: ignore[union-attr]
        except KeyError:
            return None
    return _find_in_namespaced(parent_id, namespace, _to_namespaced(model_registry))


def _to_namespaced(
    registry: Union[dict[str, ModelDefinition], ModelRegistry],
) -> dict[str, ModelDefinition]:
    """Return the registry as a key→model dict, keys unchanged.

    A ``ModelRegistry`` gives its namespaced keys; a plain dict is returned
    as-is (its keys may be ids or namespaced, per rule 6).
    """
    if hasattr(registry, "get_registry_dict"):
        return registry.get_registry_dict()  # type: ignore[union-attr]
    return registry  # type: ignore[return-value]


def _find_in_namespaced(
    model_id: str, namespace: str, mapping: dict[str, ModelDefinition]
) -> ModelDefinition | None:
    """Resolve ``model_id`` namespace-locally, then by unique match (R41).

    A plain id-keyed dict is matched directly first (rule 6).
    """
    if model_id in mapping:
        return mapping[model_id]
    local = mapping.get(f"{namespace}__{model_id}")
    if local is not None:
        return local
    candidates = [
        model for key, model in mapping.items() if key.endswith(f"__{model_id}")
    ]
    if len(candidates) == 1:
        return candidates[0]
    return None


def _model_namespace(key: str, model: ModelDefinition) -> str:
    """The namespace of a namespaced registry key, or the model's own."""
    if "__" in key:
        return key.split("__", 1)[0]
    return getattr(model, "namespace", "default") or "default"


def _model_key_in(mapping: dict[str, ModelDefinition], model: ModelDefinition) -> str:
    """The key a resolved parent is stored under (for graph/cycle output)."""
    for key, candidate in mapping.items():
        if candidate is model:
            return key
    return f"{model.namespace}__{model.id}"


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

    resolved_attributes, resolved_validations, ancestors = _resolve_sources(
        model_def, model_registry, max_depth
    )

    # Build the flattened definition without registering it (R42): model_copy
    # does not run model_post_init, so it never touches the registry. The
    # child's namespace is kept. ``extends`` is cleared, so the lineage it
    # expressed is recorded in ``ancestors``: a value typed as ``item`` must
    # still accept this model if it extends ``item`` (F62 C1).
    resolved_model = model_def.model_copy(
        update={
            "extends": [],
            "ancestors": ancestors,
            "attributes": resolved_attributes,
            "validations": resolved_validations,
        }
    )

    logger.debug(
        f"Resolved model '{model_def.id}' with {len(resolved_attributes)} attributes"
    )
    return resolved_model


def _resolve_sources(
    model_def: ModelDefinition,
    model_registry: Union[dict[str, ModelDefinition], ModelRegistry],
    max_depth: int,
) -> tuple[dict[str, AttributeDefinition], list[ValidationRule], list[str]]:
    """Merge a model's own and its ancestors' attributes and validations.

    Also returns the model's ancestors: each parent in ``extends`` order,
    followed by that parent's own ancestors, each id once (a diamond's shared
    base appears once, where it is first reached). A parent that was itself
    flattened contributes the ``ancestors`` it recorded.

    resolved(M) = merge(resolved(P1) … resolved(Pn), own(M)) in ``extends``
    order: each parent's fully resolved sources first, then M's own, each later
    source replacing an earlier attribute of the same name (R40, D11). Each
    ancestor is resolved once (a diamond does not double-merge a shared base).
    ``max_depth`` bounds the longest ``extends`` path from M (R43), and any
    cycle reachable from M raises ``InheritanceError`` naming the cycle (R44).
    """
    cache: dict[tuple[str, str], tuple[dict[str, AttributeDefinition], list]] = {}
    lineage: dict[tuple[str, str], list[str]] = {}
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
            ancestors: list[str] = []

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
                for ancestor in [
                    parent.id,
                    *parent.ancestors,
                    *lineage[(parent.namespace, parent.id)],
                ]:
                    if ancestor not in ancestors:
                        ancestors.append(ancestor)
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
            lineage[key] = ancestors
            return result
        finally:
            path.pop()

    attributes, validations = _resolve(model_def, 0)
    own_key = (model_def.namespace, model_def.id)
    ancestors = list(model_def.ancestors)
    for ancestor in lineage[own_key]:
        if ancestor not in ancestors:
            ancestors.append(ancestor)
    return attributes, validations, ancestors


def check_inheritance_conflicts(
    model_def: ModelDefinition,
    model_registry: Union[dict[str, ModelDefinition], ModelRegistry],
) -> list[str]:
    """Check for potential inheritance conflicts in a model definition.

    Accepts a ``ModelRegistry`` or a dict (plain or namespaced), and resolves
    each ancestor namespace-locally through the same lookup as inheritance
    (R45).

    Args:
        model_def: The model definition to check
        model_registry: Registry of all available model definitions

    Returns:
        List of conflict descriptions (empty if no conflicts)
    """
    conflicts: list[str] = []

    if not model_def.has_inheritance():
        return conflicts

    namespaced = _to_namespaced(model_registry)

    # Collect every chain member's attributes, resolving each namespace-locally.
    attribute_sources: dict[str, list[tuple[str, AttributeDefinition]]] = {}
    visited: set[tuple[str, str]] = set()

    def _record(source: ModelDefinition) -> None:
        for attr_name, attr_def in source.attributes.items():
            if not isinstance(attr_def, AttributeDefinition):
                attr_def = AttributeDefinition(**attr_def)
            attribute_sources.setdefault(attr_name, []).append((source.id, attr_def))

    def _visit(current: ModelDefinition) -> None:
        _record(current)
        for parent_id in current.extends:
            parent = _find_in_namespaced(parent_id, current.namespace, namespaced)
            if parent is None:
                conflicts.append(
                    f"Parent model '{parent_id}' not found in namespace "
                    f"'{current.namespace}' or uniquely elsewhere"
                )
                continue
            key = (parent.namespace, parent.id)
            if key in visited:
                continue
            visited.add(key)
            _visit(parent)

    _visit(model_def)

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
    model_registry: Union[dict[str, ModelDefinition], ModelRegistry],
) -> dict[str, set[str]]:
    """Build an inheritance graph from a model registry.

    Accepts a ``ModelRegistry`` or a dict; keys are the registry's own keys.

    Args:
        model_registry: Registry of all available model definitions

    Returns:
        Dictionary mapping model keys to their direct children's keys
    """
    mapping = _to_namespaced(model_registry)
    inheritance_graph: dict[str, set[str]] = {key: set() for key in mapping}

    for key, model_def in mapping.items():
        namespace = _model_namespace(key, model_def)
        for parent_id in model_def.extends:
            parent = _find_in_namespaced(parent_id, namespace, mapping)
            if parent is None:
                continue
            parent_key = _model_key_in(mapping, parent)
            if parent_key in inheritance_graph:
                inheritance_graph[parent_key].add(key)

    return inheritance_graph


def find_inheritance_cycles(
    model_registry: Union[dict[str, ModelDefinition], ModelRegistry],
) -> list[list[str]]:
    """Find all inheritance cycles in a model registry.

    Accepts a ``ModelRegistry`` or a dict; cycle members are namespaced keys.

    Args:
        model_registry: Registry of all available model definitions

    Returns:
        List of cycles, where each cycle is a list of namespaced model keys
    """
    mapping = _to_namespaced(model_registry)
    cycles: list[list[str]] = []
    visited: set[str] = set()
    rec_stack: set[str] = set()

    def _dfs(key: str, path: list[str]) -> None:
        if key in rec_stack:
            cycle_start = path.index(key)
            cycles.append(path[cycle_start:] + [key])
            return

        if key in visited:
            return

        visited.add(key)
        rec_stack.add(key)

        model_def = mapping[key]
        namespace = _model_namespace(key, model_def)
        for parent_id in model_def.extends:
            parent = _find_in_namespaced(parent_id, namespace, mapping)
            if parent is not None:
                _dfs(_model_key_in(mapping, parent), path + [key])

        rec_stack.remove(key)

    for key in mapping:
        if key not in visited:
            _dfs(key, [])

    return cycles


def validate_model_registry(
    model_registry: Union[dict[str, ModelDefinition], ModelRegistry],
) -> list[str]:
    """Validate a model registry for inheritance issues.

    Accepts a ``ModelRegistry`` or a dict (plain or namespaced) (R45).

    Args:
        model_registry: Registry of all available model definitions

    Returns:
        List of validation error messages (empty if valid)
    """
    namespaced = _to_namespaced(model_registry)
    errors = []

    # Check for inheritance cycles
    for cycle in find_inheritance_cycles(namespaced):
        cycle_str = " -> ".join(cycle)
        errors.append(f"Inheritance cycle detected: {cycle_str}")

    # Check for missing parent references, resolving namespace-locally
    for key, model_def in namespaced.items():
        namespace = _model_namespace(key, model_def)
        for parent_id in model_def.extends:
            if _find_in_namespaced(parent_id, namespace, namespaced) is None:
                errors.append(f"Model '{key}' extends unknown model '{parent_id}'")

    # Check for individual model inheritance conflicts
    for key, model_def in namespaced.items():
        if model_def.has_inheritance():
            for conflict in check_inheritance_conflicts(model_def, namespaced):
                errors.append(f"Model '{key}': {conflict}")

    return errors
