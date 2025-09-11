"""
Derived field resolution for grimoire-model package.

Manages derived fields and their dependencies using the Observer pattern with
topological sorting for correct evaluation order.
"""

import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Protocol, Set

from ..core.exceptions import DependencyError, TemplateResolutionError
from ..logging import get_logger

if TYPE_CHECKING:
    from ..core.schema import AttributeDefinition

logger = get_logger("resolvers.derived")


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
        self.dependency_graph: Dict[str, Set[str]] = defaultdict(
            set
        )  # field -> fields that depend on it
        self.observable_values: Dict[str, ObservableValue] = {}
        self._computing: Set[str] = set()  # Prevent circular dependencies

        # Model data access
        self._model_data: Dict[str, Any] = {}
        self._on_field_change: Optional[Callable[[str, Any], None]] = None

    def set_model_data_accessor(self, model_data: Dict[str, Any]) -> None:
        """Set the model data dictionary that this resolver will read from and
        write to."""
        self._model_data = model_data

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

        # Update dependency graph
        for dep in dependencies:
            self.dependency_graph[dep].add(field_name)

        # Create observable value if it doesn't exist
        if field_name not in self.observable_values:
            self.observable_values[field_name] = ObservableValue(field_name)

        logger.debug(f"Dependencies for {field_name}: {dependencies}")
        logger.debug(f"Updated dependency graph: {dict(self.dependency_graph)}")

    def unregister_derived_field(self, field_name: str) -> None:
        """Unregister a derived field."""
        if field_name not in self.derived_fields:
            return

        dep_info = self.derived_fields[field_name]

        # Remove from dependency graph
        for dep in dep_info.dependencies:
            self.dependency_graph[dep].discard(field_name)

        # Remove derived field
        del self.derived_fields[field_name]

        # Remove observable value
        if field_name in self.observable_values:
            del self.observable_values[field_name]

    def set_field_value(self, field_name: str, value: Any) -> None:
        """Set a field value and trigger derived field updates."""
        logger.debug(f"Setting field value: {field_name} = {value}")

        # Update model data
        self._set_nested_value(self._model_data, field_name, value)

        # Update observable value if it exists
        if field_name in self.observable_values:
            self.observable_values[field_name].value = value

        # Trigger dependent field updates
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
                value = self._convert_value_to_type(value, dep_info.attr_def)

            # Update the field value
            self._set_nested_value(self._model_data, field_name, value)

            # Update observable value
            if field_name in self.observable_values:
                self.observable_values[field_name].value = value

            # Notify callback
            if self._on_field_change:
                self._on_field_change(field_name, value)

            logger.debug(f"Computed derived field {field_name} = {value}")
            return value

        except Exception as e:
            raise TemplateResolutionError(
                f"Failed to compute derived field '{field_name}': {e}",
                template_str=dep_info.expression,
                template_variables=list(dep_info.dependencies),
            ) from e
        finally:
            self._computing.discard(field_name)

    def compute_all_derived_fields(self) -> None:
        """Compute all derived fields in dependency order."""
        logger.debug(
            f"Computing all derived fields: {list(self.derived_fields.keys())}"
        )

        if not self.derived_fields:
            return

        # Get topologically sorted order
        ordered_fields = self._topological_sort(set(self.derived_fields.keys()))
        logger.debug(f"Computing derived fields in order: {ordered_fields}")

        for field_name in ordered_fields:
            self.compute_derived_field(field_name)

    def get_field_dependencies(self, field_name: str) -> Set[str]:
        """Get the dependencies of a specific field."""
        if field_name in self.derived_fields:
            return self.derived_fields[field_name].dependencies.copy()
        return set()

    def get_dependent_fields(self, field_name: str) -> Set[str]:
        """Get fields that depend on the given field."""
        return self.dependency_graph.get(field_name, set()).copy()

    def _extract_dependencies(self, expression: str) -> Set[str]:
        """Extract variable dependencies from a template expression."""
        dependencies = set()

        # Handle $. references (current model instance)
        expression_copy = expression
        if "$." in expression:
            # Replace $.field with just field for dependency tracking
            expression_copy = re.sub(r"\$\.([a-zA-Z_]\w*)", r"\1", expression)

        # Extract variables using the template resolver
        template_vars = self.template_resolver.extract_variables(expression_copy)

        # Process template variables to extract field references
        for var in template_vars:
            # Skip built-in functions and operators
            if var in {
                "sum",
                "max",
                "min",
                "len",
                "abs",
                "round",
                "int",
                "float",
                "str",
                "bool",
            }:
                continue
            # Skip the model instance reference itself
            if var == self.instance_id:
                continue
            # Add the field dependency
            dependencies.add(var)

        # Also scan for pattern like $.field_name using regex
        dollar_pattern = re.compile(r"\$\.([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*)")
        for match in dollar_pattern.finditer(expression):
            field_ref = match.group(1)
            dependencies.add(field_ref)

        logger.debug(f"Extracted dependencies from '{expression}': {dependencies}")
        return dependencies

    def _build_template_context(self) -> Dict[str, Any]:
        """Build context for template resolution."""
        context = {
            "$": self._model_data,  # Model data accessible as $
            self.instance_id: self._model_data,  # Model data accessible by instance ID
        }

        # Add individual fields at top level for easier access
        context.update(self._model_data)

        return context

    def _convert_value_to_type(
        self, value: Any, attr_def: "AttributeDefinition"
    ) -> Any:
        """Convert a template result to the proper type based on attribute
        definition."""
        if attr_def.type == "int":
            try:
                if isinstance(value, str):
                    return int(float(value))  # Handle "15.0" -> 15
                elif isinstance(value, (int, float)):
                    return int(value)
                return value
            except (ValueError, TypeError):
                return value
        elif attr_def.type == "float":
            try:
                if isinstance(value, str):
                    return float(value)
                elif isinstance(value, (int, float)):
                    return float(value)
                return value
            except (ValueError, TypeError):
                return value
        elif attr_def.type == "bool":
            # Handle string boolean conversion (we've seen this before)
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes", "on")
            return bool(value)
        elif attr_def.type == "str":
            return str(value)
        else:
            # For other types (list, dict, etc.), return as-is
            return value

    def _topological_sort(self, fields: Set[str]) -> List[str]:
        """Sort fields in dependency order using topological sort."""
        # Build a dependency graph for just the fields we need to sort
        local_deps = {}
        for field_name in fields:
            if field_name in self.derived_fields:
                local_deps[field_name] = (
                    self.derived_fields[field_name].dependencies & fields
                )

        # Kahn's algorithm for topological sorting
        # in_degree[field] = number of dependencies this field has
        # (fields it depends on)
        in_degree = dict.fromkeys(fields, 0)
        for field_name in fields:
            if field_name in local_deps:
                in_degree[field_name] = len(local_deps[field_name])

        # Start with fields that have no dependencies (in_degree = 0)
        queue = deque([
            field_name for field_name in fields if in_degree[field_name] == 0
        ])
        result = []

        while queue:
            current_field = queue.popleft()
            result.append(current_field)

            # For each field that depends on the current field, decrease its in_degree
            if current_field in local_deps:
                for dependent_field in fields:
                    if (
                        dependent_field in local_deps
                        and current_field in local_deps[dependent_field]
                    ):
                        in_degree[dependent_field] -= 1
                        if in_degree[dependent_field] == 0:
                            queue.append(dependent_field)

        if len(result) != len(fields):
            # Circular dependency detected
            remaining = fields - set(result)
            raise DependencyError(
                f"Circular dependency detected among fields: {remaining}",
                dependency_chain=list(remaining),
            )

        return result

    def _update_dependent_fields(self, field_name: str) -> None:
        """Update all fields that depend on the given field."""
        dependent_fields = self.dependency_graph.get(field_name, set())
        if not dependent_fields:
            return

        logger.debug(f"Updating dependent fields of {field_name}: {dependent_fields}")

        # Get fields in dependency order
        ordered_fields = self._topological_sort(dependent_fields)

        for dependent_field in ordered_fields:
            if dependent_field in self.derived_fields:
                logger.debug(f"Computing derived field: {dependent_field}")
                self.compute_derived_field(dependent_field)
                # CRITICAL FIX: After recomputing a derived field, we need to update
                # its dependent fields recursively to handle dependency chains
                self._update_dependent_fields(dependent_field)

    def _on_field_updated(
        self, field_name: str, old_value: Any, new_value: Any
    ) -> None:
        """Handle field update notifications."""
        logger.debug(f"Field updated: {field_name} {old_value} -> {new_value}")
        self._update_dependent_fields(field_name)

    def _set_nested_value(self, data: Dict[str, Any], path: str, value: Any) -> None:
        """Set a nested value using dot notation."""
        if "." not in path:
            data[path] = value
            return

        keys = path.split(".")
        current = data
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value

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

            dependents = self.dependency_graph.get(current, set())
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
