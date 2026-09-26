"""
Derived field resolution for grimoire-model package.

Manages derived fields and their dependencies using the Observer pattern with
topological sorting for correct evaluation order.
"""

from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Protocol, Set

from ..core.exceptions import (
    DependencyError,
    ModelValidationError,
    TemplateResolutionError,
)
from ..core.schema import unset_as_null
from ..logging import get_logger
from .template import extract_reference_paths

if TYPE_CHECKING:
    from ..core.schema import AttributeDefinition

logger = get_logger("resolvers.derived")

_MISSING: Any = object()


def _get_by_path(data: Any, path: str) -> Any:
    """Return ``data`` at dotted ``path``, or ``_MISSING`` if absent.

    Walks ``Mapping`` values (a plain dict or a nested ``GrimoireModel``), so a
    path through a model-typed attribute resolves.
    """
    current = data
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return _MISSING
        current = current[part]
    return current


def copy_on_write_set(
    data: Dict[str, Any], path: str, value: Any, separator: str = "."
) -> Dict[str, Any]:
    """Return ``data`` with ``path`` set, copying every container on the path.

    No container reachable from ``data`` is mutated: a new dict is built for
    each level of the path, sharing everything off the path (R14). Raises
    ``TypeError`` where an intermediate key exists but is not a dict, matching
    :func:`grimoire_model.utils.paths.set_nested_value`.
    """
    if not path:
        raise ValueError("Path cannot be empty")

    if separator not in path:
        result = dict(data)
        result[path] = value
        return result

    keys = path.split(separator)
    result = dict(data)
    new_parent: Dict[str, Any] = result
    old_parent: Any = data
    for key in keys[:-1]:
        child = old_parent.get(key) if isinstance(old_parent, dict) else None
        if child is None:
            child_copy: Dict[str, Any] = {}
        elif isinstance(child, dict):
            child_copy = dict(child)
        else:
            raise TypeError(f"Cannot access key '{key}': value is not a dictionary")
        new_parent[key] = child_copy
        new_parent = child_copy
        old_parent = child
    new_parent[keys[-1]] = value
    return result


def copy_on_write_delete(
    data: Dict[str, Any], path: str, separator: str = "."
) -> Dict[str, Any]:
    """Return ``data`` with ``path`` removed, copying containers on the path.

    A missing path is returned unchanged. Like :func:`copy_on_write_set`, no
    container reachable from ``data`` is mutated (R14).
    """
    if not path:
        return data

    if separator not in path:
        if path in data:
            result = dict(data)
            del result[path]
            return result
        return data

    keys = path.split(separator)
    result = dict(data)
    new_parent: Dict[str, Any] = result
    old_parent: Any = data
    for key in keys[:-1]:
        child = old_parent.get(key) if isinstance(old_parent, dict) else None
        if not isinstance(child, dict):
            return data
        child_copy = dict(child)
        new_parent[key] = child_copy
        new_parent = child_copy
        old_parent = child
    new_parent.pop(keys[-1], None)
    return result


class TemplateResolver(Protocol):
    """Protocol for template resolution - matches the interface from template.py"""

    def resolve_template(self, template_str: str, context: Dict[str, Any]) -> Any:
        """Resolve a template string with the given context."""
        ...

    def extract_variables(self, template_str: str) -> Set[str]:
        """Extract variable names from a template string."""
        ...


@dataclass
class DependencyInfo:
    """Information about a derived field's dependencies."""

    field_name: str
    expression: str  # The template expression
    dependencies: Set[str] = field(default_factory=set)
    attr_def: Optional["AttributeDefinition"] = None  # For type conversion


class ObservableValue:
    """A value that can be observed for changes."""

    def __init__(self, field_name: str, initial_value: Any = None):
        self.field_name = field_name
        self._value = initial_value
        self._observers: List[Callable[[str, Any, Any], None]] = []

    @property
    def value(self) -> Any:
        """Get the current value."""
        return self._value

    @value.setter
    def value(self, new_value: Any) -> None:
        """Set a new value and notify observers."""
        old_value = self._value
        self._value = new_value

        # Notify observers of the change
        for observer in self._observers:
            try:
                observer(self.field_name, old_value, new_value)
            except Exception as e:
                logger.error(f"Observer error for field {self.field_name}: {e}")

    def add_observer(self, observer: Callable[[str, Any, Any], None]) -> None:
        """Add an observer that will be called when the value changes."""
        self._observers.append(observer)

    def remove_observer(self, observer: Callable[[str, Any, Any], None]) -> None:
        """Remove an observer."""
        if observer in self._observers:
            self._observers.remove(observer)


class DerivedFieldResolver:
    """Manages derived fields and their dependencies using the Observer pattern."""

    def __init__(self, template_resolver: TemplateResolver, instance_id: str = "model"):
        self.template_resolver = template_resolver
        self.instance_id = instance_id

        # Track derived fields and their dependencies
        self.derived_fields: Dict[str, DependencyInfo] = {}
        self.observable_values: Dict[str, ObservableValue] = {}
        self._computing: Set[str] = set()  # Prevent circular dependencies

        # Model data access
        self._model_data: Dict[str, Any] = {}
        self._on_field_change: Optional[Callable[[str, Any], None]] = None

        # Declared attributes, so unset optional attributes can read as None in
        # expressions (see ``unset_as_null``).
        self._declared_attributes: Dict[str, Any] = {}

        # Derived fields computed since the last ``take_recomputed``. The model
        # uses this to validate exactly the derived fields a write recomputed
        # (R16/T020).
        self._recomputed: Set[str] = set()

    def take_recomputed(self) -> Set[str]:
        """Return and clear the derived fields recomputed since the last call."""
        recomputed = self._recomputed
        self._recomputed = set()
        return recomputed

    def snapshot_state(self) -> "tuple[Dict[str, Any], Dict[str, Any]]":
        """Return the resolver state a transaction must restore on rollback.

        Storage is copy-on-write (R14), so a shallow copy of the view holds the
        old top-level bindings and every nested container they referenced is
        unchanged by a later write. Each observable value is recorded too.
        """
        view = dict(self._model_data)
        observables = {
            name: observable.value
            for name, observable in self.observable_values.items()
        }
        return view, observables

    def restore_state(self, snapshot: "tuple[Dict[str, Any], Dict[str, Any]]") -> None:
        """Restore state captured by :meth:`snapshot_state`."""
        view, observables = snapshot
        self._model_data = view
        for name, observable in self.observable_values.items():
            if name in observables:
                observable.value = observables[name]

    def set_model_data_accessor(self, model_data: Dict[str, Any]) -> None:
        """Set the model data dictionary that this resolver will read from and
        write to."""
        self._model_data = model_data

    def set_declared_attributes(self, attributes: Dict[str, Any]) -> None:
        """Set the model's declared attributes.

        Used to present unset optional attributes as None when evaluating
        expressions. Stored data is never changed by this.
        """
        self._declared_attributes = attributes

    def set_field_change_callback(self, callback: Callable[[str, Any], None]) -> None:
        """Set a callback that will be called when a derived field is computed."""
        self._on_field_change = callback

    def register_derived_field(
        self,
        field_name: str,
        expression: str,
        attr_def: Optional["AttributeDefinition"] = None,
    ) -> None:
        """Register a derived field with its expression and attribute definition."""
        logger.debug(f"Registering derived field: {field_name} = {expression}")

        # Extract dependencies from the expression
        dependencies = self._extract_dependencies(expression)

        # Create dependency info
        dep_info = DependencyInfo(
            field_name=field_name,
            expression=expression,
            dependencies=dependencies,
            attr_def=attr_def,  # Store the attribute definition for type conversion
        )
        self.derived_fields[field_name] = dep_info

        # Create observable value if it doesn't exist
        if field_name not in self.observable_values:
            self.observable_values[field_name] = ObservableValue(field_name)

        logger.debug(f"Dependencies for {field_name}: {dependencies}")

    def unregister_derived_field(self, field_name: str) -> None:
        """Unregister a derived field."""
        if field_name not in self.derived_fields:
            return

        # Remove derived field
        del self.derived_fields[field_name]

        # Remove observable value
        if field_name in self.observable_values:
            del self.observable_values[field_name]

    @staticmethod
    def _paths_overlap(a: str, b: str) -> bool:
        """Whether two reference paths overlap.

        Two paths overlap when they are equal, or one is a dotted prefix of the
        other: ``p`` and ``p.mod`` overlap; ``p.mod`` and ``p.modifier`` do not.
        """
        return a == b or a.startswith(b + ".") or b.startswith(a + ".")

    def _dependent_fields_for(self, write_path: str) -> Set[str]:
        """Every derived field whose dependencies overlap ``write_path``.

        A derived field D depends on derived field E when one of D's
        dependencies overlaps E's path. A write to ``write_path`` triggers
        every D with a dependency overlapping it.
        """
        dependents: Set[str] = set()
        for name, dep_info in self.derived_fields.items():
            if name == write_path:
                # A derived field never depends on itself.
                continue
            for dep in dep_info.dependencies:
                if self._paths_overlap(dep, write_path):
                    dependents.add(name)
                    break
        return dependents

    def _dependency_available(self, dep: str) -> bool:
        """Whether an expression can see ``dep`` (a possibly-dotted path).

        True if the path is present in the data, or if it names an unset
        optional attribute -- which reads as None (see ``unset_as_null``). A
        dependent of an optional attribute that has just been emptied must
        recompute, not keep its old value.
        """
        if _get_by_path(self._model_data, dep) is not _MISSING:
            return True
        return (
            _get_by_path(
                unset_as_null(self._model_data, self._declared_attributes), dep
            )
            is not _MISSING
        )

    def _remove_value(self, field_name: str) -> None:
        """Remove ``field_name`` (possibly dotted) from the model data view.

        The view's top-level dict is mutated in place (it is the resolver's
        own, always a fresh dict), but a nested container on the path is
        replaced rather than mutated, so a caller or a transaction snapshot
        holding it is not changed (R14).
        """
        if "." not in field_name:
            self._model_data.pop(field_name, None)
            return
        head, _, rest = field_name.partition(".")
        child = self._model_data.get(head)
        if isinstance(child, dict):
            self._model_data[head] = copy_on_write_delete(child, rest)

    def field_unset(self, field_name: str) -> None:
        """Record that a field no longer has a value, and update dependents."""
        self._remove_value(field_name)
        if field_name in self.observable_values:
            self.observable_values[field_name].value = None
        self._update_dependent_fields(field_name)

    def set_field_value(self, field_name: str, value: Any) -> None:
        """Set a field value and trigger derived field updates."""
        logger.debug(f"Setting field value: {field_name} = {value}")

        # Update model data
        self._set_nested_value(self._model_data, field_name, value)

        # Update observable value if it exists
        if field_name in self.observable_values:
            self.observable_values[field_name].value = value

        self._update_dependent_fields(field_name)

    def compute_derived_field(self, field_name: str) -> Any:
        """Compute the value of a specific derived field."""
        if field_name not in self.derived_fields:
            raise DependencyError(f"Derived field '{field_name}' not registered")

        if field_name in self._computing:
            raise DependencyError(
                f"Circular dependency detected for field '{field_name}'"
            )

        dep_info = self.derived_fields[field_name]

        try:
            self._computing.add(field_name)

            # Build template context
            context = self._build_template_context()

            # Resolve the template expression
            value = self.template_resolver.resolve_template(
                dep_info.expression, context
            )

            # Apply type conversion if we have attribute definition
            if dep_info.attr_def:
                value = self._convert_value_to_type(
                    value, dep_info.attr_def, field_name
                )

            # Update the field value
            self._set_nested_value(self._model_data, field_name, value)

            # Update observable value
            if field_name in self.observable_values:
                self.observable_values[field_name].value = value

            # Notify callback
            if self._on_field_change:
                self._on_field_change(field_name, value)

            self._recomputed.add(field_name)

            logger.debug(f"Computed derived field {field_name} = {value}")
            return value

        except ModelValidationError:
            # A bad conversion (R27) is a validation error, not a template one;
            # keep its type so callers see it as a validation failure.
            raise
        except Exception as e:
            raise TemplateResolutionError(
                f"Failed to compute derived field '{field_name}': {e}",
                template_str=dep_info.expression,
                template_variables=list(dep_info.dependencies),
            ) from e
        finally:
            self._computing.discard(field_name)

    def compute_all_derived_fields(
        self, skip_on_missing_dependencies: bool = False
    ) -> None:
        """Compute all derived fields in dependency order.

        Args:
            skip_on_missing_dependencies: If True, skip fields whose dependencies
                are not present in the model data
        """
        logger.debug(
            f"Computing all derived fields: {list(self.derived_fields.keys())}"
        )

        if not self.derived_fields:
            return

        # Get topologically sorted order
        ordered_fields = self._topological_sort(set(self.derived_fields.keys()))
        logger.debug(f"Computing derived fields in order: {ordered_fields}")

        for field_name in ordered_fields:
            if skip_on_missing_dependencies:
                # Only a missing dependency is a reason to skip; any other
                # failure raises (R26).
                dep_info = self.derived_fields[field_name]
                missing_deps = [
                    dep
                    for dep in dep_info.dependencies
                    if not self._dependency_available(dep)
                ]
                if missing_deps:
                    logger.debug(
                        f"Skipping derived field '{field_name}' due to missing "
                        f"dependencies: {missing_deps}"
                    )
                    continue

            self.compute_derived_field(field_name)

    def get_field_dependencies(self, field_name: str) -> Set[str]:
        """Get the dependencies of a specific field."""
        if field_name in self.derived_fields:
            return self.derived_fields[field_name].dependencies.copy()
        return set()

    def get_dependent_fields(self, field_name: str) -> Set[str]:
        """Get derived fields whose dependencies overlap ``field_name``."""
        return self._dependent_fields_for(field_name)

    def _extract_dependencies(self, expression: str) -> Set[str]:
        """Every maximal dotted reference path in a template expression.

        Uses the library's own Jinja2 parse (``extract_reference_paths``), not
        the injected resolver's ``extract_variables``, so dependencies are
        recorded by full path and the topological sort can order nested derived
        fields (R25, D4). The injected protocol is untouched (README L3).
        """
        dependencies = extract_reference_paths(expression)
        logger.debug(f"Extracted dependencies from '{expression}': {dependencies}")
        return dependencies

        logger.debug(f"Extracted dependencies from '{expression}': {dependencies}")
        return dependencies

    def _build_template_context(self) -> Dict[str, Any]:
        """Build context for template resolution.

        The context is the model's data and nothing else: no instance-id key,
        no builtins. An unset optional attribute reads as None; stored data is
        untouched.
        """
        return unset_as_null(self._model_data, self._declared_attributes)

    def _convert_value_to_type(
        self, value: Any, attr_def: "AttributeDefinition", field_name: str = ""
    ) -> Any:
        """Convert a template result to the attribute's declared type, exactly.

        A value that cannot be converted raises ``ModelValidationError`` naming
        the field, the expression and the value -- it is never returned
        unconverted (R27). ``None`` stays ``None`` for every type.
        """
        if value is None:
            return None

        type_name = attr_def.type
        try:
            if type_name == "int":
                return self._to_int(value)
            if type_name == "float":
                return self._to_float(value)
            if type_name == "bool":
                return self._to_bool(value)
            if type_name == "str":
                return self._to_str(value)
        except (ValueError, TypeError) as exc:
            raise ModelValidationError(
                f"Derived field '{field_name}' could not be converted to "
                f"{type_name}: {exc}",
                field_name=field_name,
                field_value=value,
                validation_errors=[
                    f"Derived value {value!r} is not a valid {type_name}"
                ],
            ) from exc

        # For other types (list, dict, model ids), return as-is.
        return value

    @staticmethod
    def _to_int(value: Any) -> int:
        """An int, an integral float (``4.0``), or a string that parses to one."""
        if isinstance(value, bool):
            raise TypeError("a bool is not an int")
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            if value.is_integer():
                return int(value)
            raise ValueError("a fractional value is not an int")
        if isinstance(value, str):
            return int(value.strip())
        raise TypeError(f"{type(value).__name__} is not an int")

    @staticmethod
    def _to_float(value: Any) -> float:
        """A number or a numeric string."""
        if isinstance(value, bool):
            raise TypeError("a bool is not a float")
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            return float(value.strip())
        raise TypeError(f"{type(value).__name__} is not a float")

    @staticmethod
    def _to_bool(value: Any) -> bool:
        """A bool, or exactly true/false/1/0/yes/no/on/off (any case)."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in ("true", "1", "yes", "on"):
                return True
            if lowered in ("false", "0", "no", "off"):
                return False
        raise ValueError("not a recognised boolean")

    @staticmethod
    def _to_str(value: Any) -> str:
        """A scalar; a container is not a string."""
        if isinstance(value, (dict, list, tuple, set)):
            raise TypeError(f"{type(value).__name__} is not a string")
        return str(value)

    def _topological_sort(self, fields: Set[str]) -> List[str]:
        """Sort fields in dependency order, deterministically.

        Derived field D depends on derived field E when one of D's dependency
        paths overlaps E's field path. Ties are broken by sorted path, so the
        order never depends on ``set`` iteration (R25).
        """
        fields = set(fields)
        local_deps: Dict[str, Set[str]] = {}
        for field_name in fields:
            deps: Set[str] = set()
            dep_info = self.derived_fields.get(field_name)
            if dep_info is not None:
                for other in fields:
                    if other == field_name:
                        continue
                    if any(
                        self._paths_overlap(dep, other) for dep in dep_info.dependencies
                    ):
                        deps.add(other)
            local_deps[field_name] = deps

        in_degree = {name: len(local_deps[name]) for name in fields}

        # Start with fields that have no dependencies (in_degree = 0). The
        # sorted seed and sorted queue make the result independent of set
        # iteration order.
        queue = deque(sorted(name for name in fields if in_degree[name] == 0))
        result = []

        while queue:
            current_field = queue.popleft()
            result.append(current_field)

            newly_ready = []
            for dependent_field in fields:
                if current_field in local_deps[dependent_field]:
                    in_degree[dependent_field] -= 1
                    if in_degree[dependent_field] == 0:
                        newly_ready.append(dependent_field)
            queue.extend(sorted(newly_ready))

        if len(result) != len(fields):
            # Circular dependency detected
            remaining = fields - set(result)
            raise DependencyError(
                f"Circular dependency detected among fields: {remaining}",
                dependency_chain=sorted(remaining),
            )

        return result

    def _update_dependent_fields(self, field_name: str) -> None:
        """Update every field whose dependencies overlap ``field_name``."""
        dependent_fields = self._dependent_fields_for(field_name)
        if not dependent_fields:
            return

        logger.debug(f"Updating dependent fields of {field_name}: {dependent_fields}")

        # Get fields in dependency order
        ordered_fields = self._topological_sort(dependent_fields)

        for dependent_field in ordered_fields:
            # Check if all dependencies are available before computing
            dep_info = self.derived_fields.get(dependent_field)
            if dep_info is None:
                continue
            missing_deps = [
                dep
                for dep in dep_info.dependencies
                if not self._dependency_available(dep)
            ]

            if missing_deps:
                # In an incremental model a dependency may not exist yet. Remove
                # the dependent's stale value rather than leave it, so it is
                # never quietly wrong (R26).
                logger.debug(
                    f"Removing derived field '{dependent_field}' whose "
                    f"dependencies are missing: {missing_deps}"
                )
                self._remove_value(dependent_field)
                if dependent_field in self.observable_values:
                    self.observable_values[dependent_field].value = None
                continue

            logger.debug(f"Computing derived field: {dependent_field}")
            self.compute_derived_field(dependent_field)
            # After recomputing a derived field, update its dependents
            # recursively to handle dependency chains.
            self._update_dependent_fields(dependent_field)

    def _on_field_updated(
        self, field_name: str, old_value: Any, new_value: Any
    ) -> None:
        """Handle field update notifications."""
        logger.debug(f"Field updated: {field_name} {old_value} -> {new_value}")
        self._update_dependent_fields(field_name)

    def _set_nested_value(self, data: Dict[str, Any], path: str, value: Any) -> None:
        """Set ``path`` in the model data view.

        The view's top-level dict is mutated in place (it is the resolver's own,
        always a fresh dict), but a nested container on the path is replaced
        rather than mutated, so a caller or a transaction snapshot holding it is
        not changed (R14).
        """
        if "." not in path:
            data[path] = value
            return

        head, _, rest = path.partition(".")
        child = data.get(head)
        child = child if isinstance(child, dict) else {}
        data[head] = copy_on_write_set(child, rest, value)

    def _get_nested_value(
        self, data: Dict[str, Any], path: str, default: Any = None
    ) -> Any:
        """Get a nested value using dot notation."""
        if "." not in path:
            return data.get(path, default)

        keys = path.split(".")
        current = data
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                return default
            current = current[key]
        return current


class BatchedDerivedFieldResolver(DerivedFieldResolver):
    """Derived field resolver that batches updates for better performance."""

    def __init__(self, template_resolver: TemplateResolver, instance_id: str = "model"):
        super().__init__(template_resolver, instance_id)
        self._batching = False
        self._pending_updates: Set[str] = set()

    def start_batch(self) -> None:
        """Start batching field updates."""
        self._batching = True
        self._pending_updates.clear()

    def end_batch(self) -> None:
        """End batching and process all pending updates."""
        if not self._batching:
            return

        self._batching = False

        if self._pending_updates:
            # Get all dependent fields
            all_dependents = set()
            for field_name in self._pending_updates:
                all_dependents.update(self._get_all_dependent_fields(field_name))

            # Compute in dependency order
            if all_dependents:
                ordered_fields = self._topological_sort(all_dependents)
                for field in ordered_fields:
                    if field in self.derived_fields:
                        self.compute_derived_field(field)

        self._pending_updates.clear()

    def abort_batch(self) -> None:
        """Discard a batch without recomputing (a rolled-back transaction).

        Balances the batch flag and clears pending updates, so a failed batch
        does not leave batching on or trigger a recompute against data that has
        just been restored.
        """
        self._batching = False
        self._pending_updates.clear()

    def set_field_value(self, field_name: str, value: Any) -> None:
        """Set field value with optional batching."""
        if self._batching:
            # Update model data but defer dependent field computation
            self._set_nested_value(self._model_data, field_name, value)
            if field_name in self.observable_values:
                self.observable_values[field_name].value = value
            self._pending_updates.add(field_name)
        else:
            # Normal processing
            super().set_field_value(field_name, value)

    def field_unset(self, field_name: str) -> None:
        """Unset a field, deferring dependent updates while batching."""
        if self._batching:
            self._remove_value(field_name)
            if field_name in self.observable_values:
                self.observable_values[field_name].value = None
            self._pending_updates.add(field_name)
        else:
            super().field_unset(field_name)

    def _get_all_dependent_fields(self, field_name: str) -> Set[str]:
        """Get all fields that transitively depend on the given field."""
        all_dependents = set()
        queue = deque([field_name])
        visited = set()

        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)

            dependents = self._dependent_fields_for(current)
            all_dependents.update(dependents)
            queue.extend(dependents)

        return all_dependents


# Factory function for easy creation
def create_derived_field_resolver(
    template_resolver: TemplateResolver,
    instance_id: str = "model",
    batched: bool = False,
) -> DerivedFieldResolver:
    """Factory function to create derived field resolvers.

    Args:
        template_resolver: Template resolver instance
        instance_id: Unique identifier for the model instance
        batched: Whether to use batched updates for better performance

    Returns:
        Configured derived field resolver instance
    """
    if batched:
        return BatchedDerivedFieldResolver(template_resolver, instance_id)
    else:
        return DerivedFieldResolver(template_resolver, instance_id)
