"""
Core GrimoireModel implementation.

Combines schema validation, template resolution, and derived field management
into a dict-like model class that integrates with grimoire-context.
"""

import uuid
from collections.abc import MutableMapping
from typing import Any, Dict, Iterator, List, Optional, Set

from pyrsistent import pmap

from ..logging import get_logger
from ..resolvers.derived import DerivedFieldResolver, create_derived_field_resolver
from ..resolvers.template import TemplateResolver, create_template_resolver
from ..utils.inheritance import resolve_model_inheritance
from ..utils.paths import (
    delete_nested_value,
    get_nested_value,
    has_nested_value,
    set_nested_value,
)
from ..validation.validators import validate_field_value, validate_model_data
from .exceptions import (
    InheritanceError,
    ModelValidationError,
)
from .schema import AttributeDefinition, ModelDefinition

logger = get_logger("core.model")


class GrimoireModel(MutableMapping):
    """A dict-like model with validation, derived fields, and inheritance support.

    Integrates with grimoire-context as a value in the context dictionary.
    """

    def __init__(
        self,
        model_definition: ModelDefinition,
        data: Optional[Dict[str, Any]] = None,
        template_resolver: Optional[TemplateResolver] = None,
        derived_field_resolver: Optional[DerivedFieldResolver] = None,
        instance_id: Optional[str] = None,
        **kwargs,
    ):
        """Initialize GrimoireModel with dependency injection.

        Args:
            model_definition: The model schema definition
            data: Initial data dictionary
            template_resolver: Template resolution service (injected dependency)
            derived_field_resolver: Derived field management service (injected
                dependency)
            instance_id: Unique identifier for this model instance
            **kwargs: Additional configuration options
        """
        self._model_def = model_definition
        self._instance_id = instance_id or str(uuid.uuid4())

        # Dependency injection - create defaults if not provided
        self._template_resolver = template_resolver or create_template_resolver()
        self._derived_field_resolver = (
            derived_field_resolver
            or create_derived_field_resolver(self._template_resolver, self._instance_id)
        )

        # Resolve inheritance to get complete schema
        self._resolved_attributes = self._resolve_inheritance()

        # Initialize data storage (immutable)
        initial_data = data or {}
        self._data = pmap(initial_data)

        # Set up derived field resolver with our data
        self._derived_field_resolver.set_model_data_accessor(dict(self._data))
        self._derived_field_resolver.set_field_change_callback(
            self._on_derived_field_changed
        )

        # Register derived fields
        self._register_derived_fields()

        # Apply defaults first
        self._apply_defaults()

        # Compute initial derived field values before validation
        # This ensures derived fields are available for validation rules
        self._derived_field_resolver.compute_all_derived_fields()

        # Validate data (including validation rules that may reference derived fields)
        self._validate_initial_data()

        logger.info(
            f"Successfully initialized model '{self._model_def.id}' "
            f"with instance ID '{self._instance_id}'"
        )

    @property
    def model_definition(self) -> ModelDefinition:
        """Get the model definition."""
        return self._model_def

    @property
    def instance_id(self) -> str:
        """Get the instance ID."""
        return self._instance_id

    def copy(self, **overrides) -> "GrimoireModel":
        """Create a copy of this model with optional data overrides."""
        new_data = dict(self._data)
        new_data.update(overrides)

        return GrimoireModel(
            model_definition=self._model_def,
            data=new_data,
            template_resolver=self._template_resolver,
            derived_field_resolver=self._derived_field_resolver,
            instance_id=self._instance_id,
        )

    # MutableMapping interface
    def __getitem__(self, key: str) -> Any:
        """Get item by key."""
        if "." in key:
            return self._get_nested_value(key)
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """Set item by key with validation and derived field updates."""
        self._set_with_validation(key, value)

    def __delitem__(self, key: str) -> None:
        """Delete item by key."""
        if "." in key:
            data_copy = dict(self._data)
            if delete_nested_value(data_copy, key):
                self._data = pmap(data_copy)
                self._derived_field_resolver.set_model_data_accessor(data_copy)
        else:
            if key in self._data:
                self._data = self._data.remove(key)
                self._derived_field_resolver.set_model_data_accessor(dict(self._data))

    def __iter__(self) -> Iterator[str]:
        """Iterate over keys."""
        return iter(self._data)

    def __len__(self) -> int:
        """Get number of items."""
        return len(self._data)

    def __contains__(self, key: Any) -> bool:
        """Check if key exists."""
        if isinstance(key, str) and "." in key:
            return self._has_nested_value(key)
        return key in self._data

    def __repr__(self) -> str:
        """String representation."""
        return f"GrimoireModel(id={self._model_def.id}, data={dict(self._data)})"

    # Extended interface for model-specific operations
    def get_attribute_definition(self, attr_name: str) -> Optional[AttributeDefinition]:
        """Get the attribute definition for a field."""
        return self._resolved_attributes.get(attr_name)

    def get_derived_fields(self) -> Set[str]:
        """Get names of all derived fields."""
        return {
            name
            for name, attr in self._resolved_attributes.items()
            if isinstance(attr, AttributeDefinition) and attr.derived
        }

    def get_field_dependencies(self, field_name: str) -> Set[str]:
        """Get the dependencies of a specific field."""
        return self._derived_field_resolver.get_field_dependencies(field_name)

    def get_dependent_fields(self, field_name: str) -> Set[str]:
        """Get fields that depend on the given field."""
        return self._derived_field_resolver.get_dependent_fields(field_name)

    def validate(self) -> List[str]:
        """Validate the current model data and return list of errors."""
        errors = []

        # Validate fields using validation engine
        field_errors = validate_model_data(dict(self._data), self._resolved_attributes)
        errors.extend(field_errors)

        # Validate model-level validation rules
        for validation_rule in self._model_def.validations:
            try:
                # Build context for validation rule
                context = self._build_validation_context()

                # Ensure the validation expression is wrapped in template syntax
                expression = validation_rule.expression
                if not self._template_resolver.is_template(expression):
                    expression = f"{{{{ {expression} }}}}"

                result = self._template_resolver.resolve_template(expression, context)

                # Validation rule should evaluate to True
                # Convert string results to boolean for proper evaluation
                if isinstance(result, str):
                    # Convert common string representations to boolean
                    if result.lower() in ("false", "0", "no", "off"):
                        result = False
                    elif result.lower() in ("true", "1", "yes", "on"):
                        result = True
                    else:
                        # Non-empty strings are truthy, empty strings are falsy
                        result = bool(result.strip())

                if not result:
                    errors.append(validation_rule.message)

            except Exception as e:
                errors.append(
                    f"Validation rule failed: {validation_rule.message} ({e})"
                )

        return errors

    def recompute_derived_fields(self) -> None:
        """Recompute all derived fields."""
        self._derived_field_resolver.compute_all_derived_fields()

    def batch_update(self, updates: Dict[str, Any]) -> None:
        """Perform batch updates to multiple fields efficiently."""
        from ..resolvers.derived import BatchedDerivedFieldResolver

        # Check if we have a batched resolver
        if isinstance(self._derived_field_resolver, BatchedDerivedFieldResolver):
            # Use batching for better performance
            self._derived_field_resolver.start_batch()

            try:
                # Apply all updates
                for key, value in updates.items():
                    self._set_with_validation(key, value, skip_derived_update=True)

                # End batching and compute derived fields
                self._derived_field_resolver.end_batch()

            except Exception:
                # Ensure batching ends even if there's an error
                self._derived_field_resolver.end_batch()
                raise
        else:
            # Regular resolver: apply updates and recompute
            for key, value in updates.items():
                self._set_with_validation(key, value, skip_derived_update=True)

            # Recompute all derived fields
            self.recompute_derived_fields()

    # Internal methods
    def _resolve_inheritance(self) -> Dict[str, AttributeDefinition]:
        """Resolve model inheritance and get complete attribute definitions."""
        if not self._model_def.has_inheritance():
            # No inheritance, return attributes as-is
            return {
                name: attr
                for name, attr in self._model_def.attributes.items()
                if isinstance(attr, AttributeDefinition)
            }

        try:
            # Resolve inheritance using global registry
            from .registry import get_default_registry

            resolved_model = resolve_model_inheritance(
                self._model_def, get_default_registry()
            )
            return {
                name: attr
                for name, attr in resolved_model.attributes.items()
                if isinstance(attr, AttributeDefinition)
            }
        except Exception as e:
            raise InheritanceError(
                f"Failed to resolve inheritance for model '{self._model_def.id}': {e}",
                model_id=self._model_def.id,
                parent_ids=self._model_def.extends,
            ) from e

    def _register_derived_fields(self) -> None:
        """Register all derived fields with the resolver."""
        for attr_name, attr_def in self._resolved_attributes.items():
            if attr_def.derived:
                self._derived_field_resolver.register_derived_field(
                    attr_name, attr_def.derived, attr_def
                )

    def _apply_defaults(self) -> None:
        """Apply default values for attributes that don't have values."""
        data_dict = dict(self._data)

        for attr_name, attr_def in self._resolved_attributes.items():
            if (
                attr_name not in data_dict
                and attr_def.default is not None
                and not attr_def.computed
            ):
                data_dict[attr_name] = attr_def.default
                logger.debug(
                    f"Applied default value for '{attr_name}': {attr_def.default}"
                )

        self._data = pmap(data_dict)
        self._derived_field_resolver.set_model_data_accessor(data_dict)

    def _validate_initial_data(self) -> None:
        """Validate initial data and raise exception if invalid."""
        errors = self.validate()
        if errors:
            raise ModelValidationError(
                f"Model validation failed for '{self._model_def.id}'",
                validation_errors=errors,
                context={
                    "model_id": self._model_def.id,
                    "instance_id": self._instance_id,
                },
            )

    def _set_with_validation(
        self, key: str, value: Any, skip_derived_update: bool = False
    ) -> None:
        """Set a field value with validation and derived field updates."""
        # Get attribute definition
        attr_def = self.get_attribute_definition(key)

        # Check if field is readonly (but allow initial setting during constructor)
        if attr_def and attr_def.readonly and key in self._data:
            raise ModelValidationError(
                f"Cannot modify readonly field '{key}'",
                field_name=key,
                field_value=value,
                validation_errors=[f"Field '{key}' is readonly and cannot be modified"],
            )

        # Validate the field if we have a definition
        if attr_def:
            errors = validate_field_value(value, key, attr_def)
            if errors:
                raise ModelValidationError(
                    f"Validation failed for field '{key}'",
                    field_name=key,
                    field_value=value,
                    validation_errors=errors,
                )

        # Update the data
        if "." in key:
            data_copy = dict(self._data)
            set_nested_value(data_copy, key, value)
            self._data = pmap(data_copy)
            self._derived_field_resolver.set_model_data_accessor(data_copy)
        else:
            self._data = self._data.set(key, value)
            self._derived_field_resolver.set_model_data_accessor(dict(self._data))

        # Update derived fields unless skipped
        if not skip_derived_update:
            self._derived_field_resolver.set_field_value(key, value)

    def _has_field(self, field_name: str) -> bool:
        """Check if a field exists in the model."""
        if "." in field_name:
            return self._has_nested_value(field_name)
        return field_name in self._data

    def _get_field_value(self, field_name: str) -> Any:
        """Get the value of a field."""
        if "." in field_name:
            return self._get_nested_value(field_name)
        return self._data.get(field_name)

    def _get_nested_value(self, path: str) -> Any:
        """Get a nested value using dot notation."""
        return get_nested_value(dict(self._data), path)

    def _set_nested_value(self, path: str, value: Any) -> None:
        """Set a nested value using dot notation."""
        data_copy = dict(self._data)
        set_nested_value(data_copy, path, value)
        self._data = pmap(data_copy)
        self._derived_field_resolver.set_model_data_accessor(data_copy)

    def _has_nested_value(self, path: str) -> bool:
        """Check if a nested value exists using dot notation."""
        return has_nested_value(dict(self._data), path)

    def _delete_nested_value(self, path: str) -> None:
        """Delete a nested value using dot notation."""
        data_copy = dict(self._data)
        if delete_nested_value(data_copy, path):
            self._data = pmap(data_copy)
            self._derived_field_resolver.set_model_data_accessor(data_copy)

    def _on_derived_field_changed(self, field_name: str, value: Any) -> None:
        """Callback when a derived field value changes."""
        # Update our data with the new derived field value
        if "." in field_name:
            self._set_nested_value(field_name, value)
        else:
            self._data = self._data.set(field_name, value)
            self._derived_field_resolver.set_model_data_accessor(dict(self._data))

    def _build_validation_context(self) -> Dict[str, Any]:
        """Build context for validation rule evaluation."""
        context = {
            "$": dict(self._data),
            self._instance_id: dict(self._data),
        }

        # Add individual fields at top level
        context.update(dict(self._data))

        return context

    def __eq__(self, other: Any) -> bool:
        """Test equality with another object."""
        if not isinstance(other, GrimoireModel):
            return False
        return self._model_def == other._model_def and dict(self._data) == dict(
            other._data
        )

    def __hash__(self) -> int:
        """Make GrimoireModel hashable."""
        return hash((self._model_def.id, tuple(sorted(dict(self._data).items()))))


# Factory function for easy model creation
def create_model(
    model_definition: ModelDefinition,
    data: Optional[Dict[str, Any]] = None,
    template_resolver_type: str = "jinja2",
    **kwargs,
) -> GrimoireModel:
    """Factory function to create GrimoireModel instances.

    Args:
        model_definition: The model schema definition
        data: Initial model data
        template_resolver_type: Type of template resolver to use
        **kwargs: Additional configuration options

    Returns:
        Configured GrimoireModel instance
    """
    template_resolver = create_template_resolver(
        resolver_type=template_resolver_type,
        **kwargs.pop("template_resolver_kwargs", {}),
    )

    derived_resolver = create_derived_field_resolver(
        template_resolver=template_resolver, **kwargs.pop("derived_resolver_kwargs", {})
    )

    return GrimoireModel(
        model_definition=model_definition,
        data=data,
        template_resolver=template_resolver,
        derived_field_resolver=derived_resolver,
        **kwargs,
    )
