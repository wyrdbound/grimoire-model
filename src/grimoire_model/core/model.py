"""
Core GrimoireModel implementation.

Combines schema validation, template resolution, and derived field management
into a dict-like model class that integrates with grimoire-context.
"""

import copy as _copy
import threading
import uuid
from collections.abc import Mapping, MutableMapping
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Optional, Set, Tuple

from pyrsistent import pmap

from ..logging import get_logger
from ..resolvers.derived import (
    DerivedFieldResolver,
    copy_on_write_delete,
    copy_on_write_set,
    create_derived_field_resolver,
)
from ..resolvers.template import TemplateResolver, create_template_resolver
from ..utils.inheritance import resolve_model_inheritance
from ..utils.paths import (
    get_nested_value,
    has_nested_value,
)
from ..validation.validators import validate_field_value, validate_model_data
from .exceptions import (
    InheritanceError,
    ModelValidationError,
)
from .schema import (
    BASIC_TYPES,
    AttributeDefinition,
    ModelDefinition,
    iter_leaf_attributes,
    unset_as_null,
)

if TYPE_CHECKING:
    from .registry import ModelRegistry

logger = get_logger("core.model")


def _make_derived_resolver_like(
    resolver: DerivedFieldResolver,
) -> DerivedFieldResolver:
    """Build a fresh derived-field resolver of the same kind as ``resolver``.

    A copy must not share its resolver with the original: the resolver holds
    the data view and the change callback, and re-pointing them at the copy
    makes the original's writes recompute into the copy (R15). Batched stays
    batched.
    """
    from ..resolvers.derived import BatchedDerivedFieldResolver

    return create_derived_field_resolver(
        template_resolver=resolver.template_resolver,
        batched=isinstance(resolver, BatchedDerivedFieldResolver),
    )


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
        skip_initial_validation: bool = False,
        registry: Optional["ModelRegistry"] = None,
    ):
        """Initialize GrimoireModel with dependency injection.

        Args:
            model_definition: The model schema definition
            data: Initial data dictionary
            template_resolver: Template resolution service (injected dependency)
            derived_field_resolver: Derived field management service (injected
                dependency)
            instance_id: Unique identifier for this model instance
            skip_initial_validation: If True, skip validation during initialization
            registry: Model registry for inheritance and type lookup (default:
                the global registry). Nested models inherit it.
        """
        # Every public read and write takes this lock, so a model is safe to
        # share across threads (AGENTS.md AI Guidance §10). It is re-entrant:
        # a derived-field callback and a nested-model write re-enter.
        self._lock = threading.RLock()

        self._model_def = model_definition
        self._instance_id = instance_id or str(uuid.uuid4())
        self._skip_initial_validation = skip_initial_validation

        if registry is None:
            from .registry import get_default_registry

            registry = get_default_registry()
        self._registry = registry

        # Dependency injection - create defaults if not provided
        self._template_resolver = template_resolver or create_template_resolver()
        self._derived_field_resolver = (
            derived_field_resolver
            or create_derived_field_resolver(self._template_resolver, self._instance_id)
        )

        # Resolve inheritance to get complete schema, and the lineage that a
        # value typed as an ancestor is checked against (``is_a``).
        self._resolved_attributes, self._ancestors = self._resolve_inheritance()

        # Initialize data storage (immutable). Null on an optional attribute
        # means "no value", which is stored as absence.
        initial_data = self._without_null_optionals(
            data or {}, self._resolved_attributes
        )
        self._data = pmap(initial_data)

        # Instantiate nested models before setting up resolvers
        self._instantiate_nested_models()

        # Set up derived field resolver with our data
        self._derived_field_resolver.set_declared_attributes(self._resolved_attributes)
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
        # If skipping validation, also skip derived fields with missing dependencies
        self._derived_field_resolver.compute_all_derived_fields(
            skip_on_missing_dependencies=skip_initial_validation
        )

        # Validate data (including validation rules that may reference derived fields)
        if not skip_initial_validation:
            self._validate_initial_data()

        logger.debug(
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

    def is_a(self, model_id: str) -> bool:
        """Whether this model is ``model_id`` or inherits from it.

        A value typed as a model accepts that model or any model that extends
        it, directly or through its own parents: a ``weapon`` that extends
        ``item`` is an ``item``. Ids are compared the way ``type`` names them.
        """
        return model_id == self._model_def.id or model_id in self._ancestors

    def copy(self, **overrides) -> "GrimoireModel":
        """Create an independent copy of this model with optional data overrides.

        The copy gets its own derived-field resolver (of the same kind as this
        model's) and its own instance id, so a later write to either model
        recomputes only that model. The template resolver is shared: it is
        stateless apart from its lock-protected cache. The copy is built in the
        same validation mode as the original.
        """
        with self._lock:
            new_data = dict(self._data)
            new_data.update(overrides)

            derived_resolver = _make_derived_resolver_like(self._derived_field_resolver)

            return GrimoireModel(
                model_definition=self._model_def,
                data=new_data,
                template_resolver=self._template_resolver,
                derived_field_resolver=derived_resolver,
                skip_initial_validation=self._skip_initial_validation,
            )

    # MutableMapping interface
    def __getitem__(self, key: str) -> Any:
        """Get item by key.

        A container read (a dict, list or nested model) is returned as an
        independent copy, so a caller cannot mutate the model's storage through
        what it was handed (R14, D2). Scalars are returned as they are.
        """
        with self._lock:
            if "." in key:
                return self._read_value(self._get_nested_value(key))
            return self._read_value(self._data[key])

    @classmethod
    def _read_value(cls, value: Any) -> Any:
        """Return a value safe to hand to a caller (R14).

        A nested ``GrimoireModel`` is copied with ``copy()`` (independent since
        T016); a ``dict`` or ``list`` is copied recursively, so a nested model
        or container inside one is handled; a scalar is returned as is. Internal
        reads (contexts, validation) use ``_data`` directly and do not pay this
        cost.
        """
        if isinstance(value, GrimoireModel):
            return value.copy()
        if isinstance(value, dict):
            return {key: cls._read_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._read_value(item) for item in value]
        return value

    def __setitem__(self, key: str, value: Any) -> None:
        """Set item by key with validation and derived field updates."""
        with self._lock:
            self._set_with_validation(key, value)

    def __delitem__(self, key: str) -> None:
        """Delete an item, following the write rules (R19).

        An optional attribute is unset (exactly ``model[key] = None``); a
        required, readonly or derived attribute raises ``ModelValidationError``.
        An undeclared or absent key raises ``KeyError`` (the ``MutableMapping``
        contract). Dependents of an unset attribute recompute.
        """
        with self._lock:
            self._delitem_locked(key)

    def _delitem_locked(self, key: str) -> None:
        """``__delitem__`` body, run under the lock."""
        attr_def = self.get_attribute_definition(key)

        if attr_def is None:
            raise KeyError(key)

        if attr_def.derived:
            raise ModelValidationError(
                f"Cannot delete derived field '{key}'",
                field_name=key,
                validation_errors=[f"Field '{key}' is derived and cannot be deleted"],
            )
        if attr_def.readonly:
            raise ModelValidationError(
                f"Cannot delete readonly field '{key}'",
                field_name=key,
                validation_errors=[f"Field '{key}' is readonly and cannot be deleted"],
            )
        if not attr_def.optional:
            raise ModelValidationError(
                f"Cannot delete required field '{key}'",
                field_name=key,
                validation_errors=[f"Field '{key}' is required and cannot be deleted"],
            )

        if not self._has_field(key):
            raise KeyError(key)
        self._unset_field(key)

    def __iter__(self) -> Iterator[str]:
        """Iterate over a snapshot of the keys."""
        with self._lock:
            return iter(list(self._data))

    def __len__(self) -> int:
        """Get number of items."""
        with self._lock:
            return len(self._data)

    def __contains__(self, key: Any) -> bool:
        """Check if key exists."""
        with self._lock:
            if isinstance(key, str) and "." in key:
                return self._has_nested_value(key)
            return key in self._data

    def __repr__(self) -> str:
        """String representation."""
        return f"GrimoireModel(id={self._model_def.id}, data={dict(self._data)})"

    def __getattr__(self, name: str) -> Any:
        """Provide attribute-style access to model data.

        This enables both dictionary-style (`obj['name']`) and attribute-style
        (`obj.name`) access to model fields, improving compatibility with
        template engines like Jinja2 and following standard Python object patterns.

        Args:
            name: The attribute name to access

        Returns:
            The value of the model field if it exists in the resolved attributes

        Raises:
            AttributeError: If the attribute is not a defined model field
        """
        # Check if it's a defined attribute in the model
        # We need to check if _resolved_attributes exists first to avoid infinite
        # recursion during object initialization
        if (
            "_resolved_attributes" in self.__dict__
            and name in self._resolved_attributes
        ):
            return self.get(name)

        # Fall back to normal AttributeError for undefined attributes
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )

    def __setattr__(self, name: str, value: Any) -> None:
        """Handle attribute assignment.

        Enables both dictionary-style and attribute-style assignment to model fields.
        Internal attributes (starting with '_') and special attributes are handled
        normally, while model data attributes are routed through the validation system.

        Args:
            name: The attribute name to set
            value: The value to assign
        """
        # Handle internal attributes normally (those starting with '_')
        if name.startswith("_"):
            super().__setattr__(name, value)
        # Handle model data attributes (if _resolved_attributes exists and
        # name is in it)
        elif (
            "_resolved_attributes" in self.__dict__
            and name in self._resolved_attributes
        ):
            self[name] = value
        else:
            # For any other attributes, use default behavior
            super().__setattr__(name, value)

    # Extended interface for model-specific operations
    def get_attribute_definition(self, attr_name: str) -> Optional[AttributeDefinition]:
        """Get the attribute definition for a field.

        A dotted name (``power.score``) is resolved through anonymous nested
        groups, so writes to a nested leaf are validated like any other write.
        A path into a named nested model returns None; that model validates its
        own attributes.
        """
        parts = attr_name.split(".")
        attributes: Dict[str, AttributeDefinition] = self._resolved_attributes
        for part in parts[:-1]:
            group = attributes.get(part)
            if group is None or not group.attributes:
                return None
            attributes = group.attributes
        return attributes.get(parts[-1])

    def get_derived_fields(self) -> Set[str]:
        """Get the dotted paths of all derived fields, including group leaves."""
        return {
            path
            for path, attr in iter_leaf_attributes(self._resolved_attributes)
            if attr.derived
        }

    def get_field_dependencies(self, field_name: str) -> Set[str]:
        """Get the dependencies of a specific field."""
        return self._derived_field_resolver.get_field_dependencies(field_name)

    def get_dependent_fields(self, field_name: str) -> Set[str]:
        """Get fields that depend on the given field."""
        return self._derived_field_resolver.get_dependent_fields(field_name)

    def validate(self) -> List[str]:
        """Validate the current model data and return list of errors."""
        with self._lock:
            return self._validate_locked()

    def _validate_locked(self) -> List[str]:
        """``validate`` body, run under the lock."""
        errors = []

        # Validate fields using validation engine. Templated ranges
        # (e.g. "0..{{ max_hp }}") are resolved against the current data
        # first, so the validators stay context-free.
        attributes = self._resolve_templated_ranges(self._resolved_attributes)
        field_errors = validate_model_data(dict(self._data), attributes)
        errors.extend(field_errors)

        errors.extend(self._validate_nested_models())
        errors.extend(self._validate_model_rules())

        return errors

    def _validate_nested_models(self) -> List[str]:
        """Errors from nested models, prefixed with the path to each (R35)."""
        errors: List[str] = []
        for path, value in self._iter_nested_model_values():
            for error in value.validate():
                errors.append(f"{path}: {error}")
        return errors

    def _iter_nested_model_values(self) -> Iterator[Tuple[str, "GrimoireModel"]]:
        """Yield ``(dotted_path, nested_model)`` for every built nested model."""
        for path, attr_def in iter_leaf_attributes(self._resolved_attributes):
            value = self._get_field_value(path)
            if isinstance(value, GrimoireModel):
                yield path, value
            elif (
                attr_def.type == "list"
                and attr_def.of
                and attr_def.of not in BASIC_TYPES
                and isinstance(value, list)
            ):
                for index, element in enumerate(value):
                    if isinstance(element, GrimoireModel):
                        yield f"{path}[{index}]", element

    def _validate_model_rules(self) -> List[str]:
        """Errors from the model's own ``validations`` rules."""
        errors: List[str] = []

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
        with self._lock:
            self._derived_field_resolver.compute_all_derived_fields()

    def batch_update(self, updates: Dict[str, Any]) -> None:
        """Apply several writes as one transaction (R17, D3).

        Each target is checked (readonly and derived are rejected before
        anything is applied); the writes are staged without per-field
        validation; dependents are recomputed once; then every written leaf is
        validated against the **recomputed** data, every recomputed derived
        field against its own constraints, and — for a validated model — the
        model-level rules. Any failure restores the model and raises.
        """
        with self._lock:
            self._batch_update_locked(updates)

    def _batch_update_locked(self, updates: Dict[str, Any]) -> None:
        """``batch_update`` body, run under the lock."""
        from ..resolvers.derived import BatchedDerivedFieldResolver

        for key in updates:
            self._reject_unwritable(key)

        data_snapshot = self._data
        resolver_snapshot = self._derived_field_resolver.snapshot_state()
        self._derived_field_resolver.take_recomputed()

        batched = self._derived_field_resolver
        batch = batched if isinstance(batched, BatchedDerivedFieldResolver) else None
        if batch is not None:
            batch.start_batch()

        try:
            for key, value in updates.items():
                # Let the resolver see each write. A batched resolver defers the
                # recompute to end_batch; a plain one recomputes per write, and
                # recompute_derived_fields runs once more below; either way the
                # final values are computed from all the batch's writes.
                self._apply_write(
                    key, value, skip_derived_update=False, validate_leaf=False
                )

            if batch is not None:
                batch.end_batch()
            else:
                self.recompute_derived_fields()

            errors = self._validate_batch(updates)
            if errors:
                raise ModelValidationError(
                    "Batch update left the model invalid",
                    validation_errors=errors,
                )
        except Exception:
            if batch is not None:
                # Balance the batch flag without recomputing a rolled-back state.
                batch.abort_batch()
            self._data = data_snapshot
            self._derived_field_resolver.restore_state(resolver_snapshot)
            raise

    def _reject_unwritable(self, key: str) -> None:
        """Reject a write to a derived, or already-valued readonly, attribute."""
        attr_def = self.get_attribute_definition(key)
        if attr_def is not None and attr_def.derived:
            raise ModelValidationError(
                f"Cannot write to derived field '{key}'",
                field_name=key,
                validation_errors=[f"Field '{key}' is derived and cannot be written"],
            )
        if attr_def is not None and attr_def.readonly and self._has_field(key):
            raise ModelValidationError(
                f"Cannot modify readonly field '{key}'",
                field_name=key,
                validation_errors=[f"Field '{key}' is readonly and cannot be modified"],
            )

    def _validate_batch(self, updates: Dict[str, Any]) -> List[str]:
        """Errors from a batch: written leaves, recomputed fields, model rules."""
        errors: List[str] = []

        for key, value in updates.items():
            attr_def = self.get_attribute_definition(key)
            if attr_def is None:
                continue
            resolved = self._resolve_templated_ranges({key: attr_def})[key]
            errors.extend(validate_field_value(value, key, resolved))
        if errors:
            return errors

        errors.extend(self._validate_recomputed_fields())
        if errors:
            return errors

        if not self._skip_initial_validation:
            errors.extend(self._validate_model_rules())
        return errors

    def _validate_recomputed_fields(self) -> List[str]:
        """Errors from the derived fields recomputed since the last take."""
        errors: List[str] = []
        for path in sorted(self._derived_field_resolver.take_recomputed()):
            attr_def = self.get_attribute_definition(path)
            if attr_def is None:
                continue
            resolved = self._resolve_templated_ranges({path: attr_def})[path]
            value = self._get_field_value(path)
            errors.extend(validate_field_value(value, path, resolved))
            if errors:
                return errors
        return errors

    # Internal methods
    def _resolve_inheritance(
        self,
    ) -> Tuple[Dict[str, AttributeDefinition], Tuple[str, ...]]:
        """Resolve inheritance: the complete attribute definitions, and every
        model this one inherits from.

        A definition that was already flattened (``extends: []``) keeps the
        ``ancestors`` recorded when it was resolved.
        """
        if not self._model_def.has_inheritance():
            # No inheritance, return attributes as-is
            return (
                {
                    name: attr
                    for name, attr in self._model_def.attributes.items()
                    if isinstance(attr, AttributeDefinition)
                },
                tuple(self._model_def.ancestors),
            )

        try:
            resolved_model = resolve_model_inheritance(self._model_def, self._registry)
            return (
                {
                    name: attr
                    for name, attr in resolved_model.attributes.items()
                    if isinstance(attr, AttributeDefinition)
                },
                tuple(resolved_model.ancestors),
            )
        except Exception as e:
            raise InheritanceError(
                f"Failed to resolve inheritance for model '{self._model_def.id}': {e}",
                model_id=self._model_def.id,
                parent_ids=self._model_def.extends,
            ) from e

    def _is_custom_model_type(self, type_name: str) -> bool:
        """Check if a type name refers to a custom model rather than a primitive.

        Args:
            type_name: The type name to check

        Returns:
            True if this is a custom model type, False if it's a primitive type
        """
        from .primitive_registry import get_default_primitive_registry
        from .schema import BASIC_TYPES

        # A basic type is the spec's type, exact case. A name that differs only
        # in case (``Int``) is a model id, not a primitive.
        if type_name in BASIC_TYPES:
            return False

        # Check registered custom primitives
        primitive_registry = get_default_primitive_registry()
        if primitive_registry.is_registered(type_name):
            return False

        # Must be a custom model type
        return True

    def _resolve_model_type(self, type_name: str) -> ModelDefinition:
        """Resolve a custom type name to a ModelDefinition.

        Args:
            type_name: The type name to resolve

        Returns:
            The ModelDefinition if found

        Raises:
            ModelValidationError: If the type name cannot be resolved to a
                registered model definition
        """
        try:
            return self._registry.lookup(type_name, self._model_def.namespace)
        except KeyError as exc:
            raise ModelValidationError(
                f"Invalid model type '{type_name}' in model '{self._model_def.id}': "
                f"{exc}",
                context={
                    "model_id": self._model_def.id,
                    "type_name": type_name,
                    "namespace": self._model_def.namespace,
                },
            ) from exc

    def _model_typed_attribute(self, name: str) -> Optional[AttributeDefinition]:
        """The attribute definition at ``name`` if its type is a model.

        The counterpart to :meth:`get_attribute_definition` for writes: a
        **model-typed** attribute (``abilities``) is not a group of leaf
        definitions but a nested model, and a write beneath it belongs to that
        model. Returns ``None`` for a primitive, an anonymous group or an
        unknown name.
        """
        attr_def = self._resolved_attributes.get(name)
        if attr_def is None or not attr_def.type:
            return None
        if not self._is_custom_model_type(attr_def.type):
            return None
        return attr_def

    def _model_typed_prefix(
        self, key: str
    ) -> Optional[Tuple[str, AttributeDefinition, str]]:
        """The shortest dotted prefix of ``key`` that is a model-typed attribute.

        Walks the path from the root, so a model-typed leaf inside an anonymous
        group (``abilities.con``) is found, not just a top-level one (R34).
        Returns ``(prefix, definition, remainder)`` or ``None`` when no prefix
        is model-typed.
        """
        parts = key.split(".")
        attributes: Dict[str, AttributeDefinition] = self._resolved_attributes
        for index in range(len(parts) - 1):
            attr_def = attributes.get(parts[index])
            if attr_def is None:
                return None
            if self._is_custom_model_type(attr_def.type):
                return (
                    ".".join(parts[: index + 1]),
                    attr_def,
                    ".".join(parts[index + 1 :]),
                )
            if not attr_def.attributes:
                return None
            attributes = attr_def.attributes
        return None

    def _nested_model(
        self,
        name: str,
        attr_def: AttributeDefinition,
        data: Optional[Dict[str, Any]] = None,
    ) -> "GrimoireModel":
        """The nested model at top-level ``name``, built from ``data`` if needed.

        An existing nested ``GrimoireModel`` is returned unchanged, so a dotted
        write into an already-built attribute descends into it rather than
        replacing it. A plain mapping — the shape a write produces before this
        fix — is wrapped into the model, which computes its derived fields.
        ``data`` is only used to build a model where none exists yet.
        """
        if data is None:
            current = self._data.get(name)
            if isinstance(current, GrimoireModel):
                return current
            if current is None:
                data = {}
            elif isinstance(current, dict):
                data = dict(current)
            else:
                raise TypeError(
                    f"Cannot write into '{name}': it holds a "
                    f"{type(current).__name__}, not a model"
                )
        return self._make_nested_model(attr_def, data)

    def _nested_model_at(
        self, prefix: str, attr_def: AttributeDefinition
    ) -> "GrimoireModel":
        """The nested model at dotted ``prefix`` (possibly inside a group).

        Descends through anonymous groups; a mapping there is wrapped into the
        model (R34).
        """
        current: Any = self._data
        for part in prefix.split("."):
            if isinstance(current, GrimoireModel):
                current = current._raw_data().get(part)
            elif isinstance(current, Mapping):
                current = current.get(part)
            else:
                current = None
        if isinstance(current, GrimoireModel):
            return current
        if current is None:
            data: Dict[str, Any] = {}
        elif isinstance(current, dict):
            data = dict(current)
        else:
            raise TypeError(
                f"Cannot write into '{prefix}': it holds a "
                f"{type(current).__name__}, not a model"
            )
        return self._make_nested_model(attr_def, data)

    def _make_nested_model(
        self, attr_def: AttributeDefinition, data: Dict[str, Any]
    ) -> "GrimoireModel":
        """Build a nested model as a partial.

        A dotted write reaches one leaf, and the nested model's other required
        attributes are supplied later or not at all. Derived fields compute from
        what is present; the parent's full validation still runs when the whole
        is validated.
        """
        return GrimoireModel(
            model_definition=self._resolve_model_type(attr_def.type),
            data=dict(data),
            template_resolver=self._template_resolver,
            skip_initial_validation=True,
            registry=self._registry,
        )

    def _raw_data(self) -> Dict[str, Any]:
        """This model's live data, for internal navigation (no copy)."""
        return dict(self._data)

    def _instantiate_nested_models(self) -> None:
        """Recursively instantiate nested data as GrimoireModel objects.

        This method walks through the data dictionary and for any attribute
        that has a custom model type, it instantiates the nested data as a
        GrimoireModel object with its own derived fields computed. A list whose
        ``of`` names a model has each element built (D16).
        """
        data_dict = dict(self._data)
        modified = False

        for attr_path, attr_def in self._iter_attribute_paths(
            self._resolved_attributes
        ):
            built = self._build_nested_at(data_dict, attr_path, attr_def)
            if built:
                modified = True

        # Update the data if we instantiated any nested models
        if modified:
            self._data = pmap(data_dict)

    def _build_nested_at(
        self, data_dict: Dict[str, Any], attr_path: str, attr_def: AttributeDefinition
    ) -> bool:
        """Build the model-typed value at dotted ``attr_path`` in ``data_dict``.

        Walks through anonymous groups; a model-typed leaf inside a group is
        built exactly as a top-level model-typed attribute is (R34). Returns
        True if a value was replaced.
        """
        parts = attr_path.split(".")
        current: Any = data_dict
        for part in parts[:-1]:
            if not isinstance(current, dict) or part not in current:
                return False
            current = current[part]
            if not isinstance(current, dict):
                return False

        leaf = parts[-1]
        if not isinstance(current, dict) or leaf not in current:
            return False
        value = current[leaf]
        if value is None:
            return False

        if attr_def.type == "list" and attr_def.of:
            built = self._build_list_value(attr_def, value, attr_path)
        elif self._is_custom_model_type(attr_def.type):
            built = self._build_model_value(attr_def, value, attr_path)
        else:
            return False

        if built is value:
            return False
        current[leaf] = built
        return True

    def _build_model_value(
        self, attr_def: AttributeDefinition, value: Any, path: str
    ) -> "GrimoireModel":
        """Build ``value`` as the model ``attr_def.type`` names.

        A mapping is built into that model. A ``GrimoireModel`` of that model,
        or of any model that extends it (``is_a``), is returned as it is: a
        ``weapon`` is an ``item``, and keeps its own attributes and derived
        fields (F62 C1). Any other model, or anything that is neither, raises
        ``ModelValidationError`` (R32). ``path`` names the attribute in errors
        (a list element is ``inv[0]``).

        A mapping carries no type of its own, so it is always built as the
        declared model; subtype *data* is not inferred from its keys.
        """
        nested_model_def = self._resolve_model_type(attr_def.type)

        if isinstance(value, GrimoireModel):
            if not value.is_a(nested_model_def.id):
                raise ModelValidationError(
                    f"Attribute '{path}' must be a model of type "
                    f"'{nested_model_def.id}' or a model that extends it, got "
                    f"'{value.model_definition.id}'",
                    field_name=path,
                    field_value=value,
                )
            return value

        if not isinstance(value, Mapping):
            raise ModelValidationError(
                f"Attribute '{path}' must be a mapping or a "
                f"'{attr_def.type}' model, got {type(value).__name__}",
                field_name=path,
                field_value=value,
            )

        nested_model = GrimoireModel(
            model_definition=nested_model_def,
            data=dict(value),
            template_resolver=self._template_resolver,
            skip_initial_validation=self._skip_initial_validation,
            registry=self._registry,
        )
        logger.debug(f"Instantiated nested model '{path}' of type '{attr_def.type}'")
        return nested_model

    def _build_list_value(
        self, attr_def: AttributeDefinition, value: Any, path: str
    ) -> Any:
        """Validate a list and build model-typed elements (R33, D16).

        A primitive ``of`` validates each element with an indexed path; a
        model-id ``of`` builds each mapping element as that model, keeps an
        element that is already a model of that id, and rejects anything else,
        errors named ``path[i]``.
        """
        if not isinstance(value, list):
            raise ModelValidationError(
                f"Attribute '{path}' must be a list, got {type(value).__name__}",
                field_name=path,
                field_value=value,
            )

        if attr_def.of is None or attr_def.of in BASIC_TYPES:
            return value

        element_def = AttributeDefinition(type=attr_def.of)
        built_elements: List[Any] = []
        for index, element in enumerate(value):
            if element is None:
                built_elements.append(element)
                continue
            try:
                built_elements.append(
                    self._build_model_value(element_def, element, f"{path}[{index}]")
                )
            except ModelValidationError as exc:
                # Name the element by its indexed path (R33).
                raise ModelValidationError(
                    f"Invalid element {path}[{index}]: {exc.message}",
                    field_name=f"{path}[{index}]",
                    field_value=element,
                    validation_errors=exc.validation_errors
                    or [f"'{path}[{index}]' is invalid"],
                ) from exc
        return built_elements

    @staticmethod
    def _without_null_optionals(
        data: Dict[str, Any], attributes: Dict[str, AttributeDefinition]
    ) -> Dict[str, Any]:
        """Drop ``None`` values of optional attributes, recursing into groups.

        An optional attribute with no value is stored as absent, never as None.
        ``None`` on a required attribute is left in place so validation reports
        it. ``data`` is not modified.
        """
        result: Dict[str, Any] = {}
        for key, value in data.items():
            attr = attributes.get(key)
            if attr is not None and value is None and attr.optional:
                continue
            if attr is not None and attr.attributes and isinstance(value, dict):
                value = GrimoireModel._without_null_optionals(value, attr.attributes)
            result[key] = value
        return result

    @staticmethod
    def _iter_attribute_paths(
        attributes: Dict[str, "AttributeDefinition"], prefix: str = ""
    ) -> Iterator[Tuple[str, "AttributeDefinition"]]:
        """Yield ``(dotted_path, definition)`` for every leaf attribute."""
        return iter_leaf_attributes(attributes, prefix)

    def _register_derived_fields(self) -> None:
        """Register all derived fields with the resolver, including nested ones."""
        for attr_path, attr_def in self._iter_attribute_paths(
            self._resolved_attributes
        ):
            if attr_def.derived:
                self._derived_field_resolver.register_derived_field(
                    attr_path, attr_def.derived, attr_def
                )

    def _apply_defaults(self) -> None:
        """Apply default values for attributes that don't have values."""
        data_dict = dict(self._data)

        for attr_path, attr_def in self._iter_attribute_paths(
            self._resolved_attributes
        ):
            if attr_def.default is None or attr_def.computed:
                continue

            parts = attr_path.split(".")
            target = data_dict
            for part in parts[:-1]:
                existing = target.get(part)
                if not isinstance(existing, dict):
                    existing = {} if existing is None else existing
                    if not isinstance(existing, dict):
                        break
                    target[part] = existing
                target = existing
            else:
                leaf = parts[-1]
                if leaf not in target:
                    target[leaf] = _copy.deepcopy(attr_def.default)
                    logger.debug(
                        f"Applied default value for '{attr_path}': {attr_def.default}"
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
        """Set a field value as a transaction.

        The write is validated, applied, its dependents recomputed, and the
        recomputed derived fields (and, for a validated model, the model-level
        ``validations``) checked. Any failure restores the model exactly and
        raises ``ModelValidationError``, so a write never leaves the model
        violating a constraint (R16, D3).
        """
        data_snapshot = self._data
        resolver_snapshot = self._derived_field_resolver.snapshot_state()
        self._derived_field_resolver.take_recomputed()

        try:
            self._apply_write(key, value, skip_derived_update)

            if not skip_derived_update:
                errors = self._validate_after_write()
                if errors:
                    raise ModelValidationError(
                        f"Write to '{key}' left the model invalid",
                        field_name=key,
                        field_value=value,
                        validation_errors=errors,
                    )
        except Exception:
            self._data = data_snapshot
            self._derived_field_resolver.restore_state(resolver_snapshot)
            raise

    def _validate_after_write(self) -> List[str]:
        """Errors from a write: recomputed derived fields, then model rules.

        An incremental model (``create_model_without_validation``) checks the
        leaf and the recomputed derived fields only; a rule over required
        attributes cannot pass mid-build, so whole-model rules are left to an
        explicit ``validate()``.
        """
        errors: List[str] = []

        errors.extend(self._validate_recomputed_fields())
        if errors:
            return errors

        if not self._skip_initial_validation:
            errors.extend(self._validate_model_rules())

        return errors

    def _apply_write(
        self,
        key: str,
        value: Any,
        skip_derived_update: bool,
        validate_leaf: bool = True,
    ) -> None:
        """Apply a single write; the body of :meth:`_set_with_validation`.

        ``validate_leaf`` is False while staging a batch: a templated range
        resolved against data the batch's own writes have not recomputed yet
        would fail spuriously, so validation happens once, after recompute
        (:meth:`_validate_batch`).
        """
        # Get attribute definition
        attr_def = self.get_attribute_definition(key)

        # An undeclared write is an error (R21, D6). A path into a nested
        # *model* is that model's business -- the head there is a declared
        # model-typed attribute, resolved below.
        if not self._declares(key):
            raise ModelValidationError(
                f"Cannot write to undeclared attribute '{key}'",
                field_name=key,
                field_value=value,
                validation_errors=[f"'{key}' is not a declared attribute"],
            )

        # A derived attribute is not writable at any path (R18). The derived
        # resolver writes computed values directly, not through this method.
        if attr_def is not None and attr_def.derived:
            raise ModelValidationError(
                f"Cannot write to derived field '{key}'",
                field_name=key,
                field_value=value,
                validation_errors=[f"Field '{key}' is derived and cannot be written"],
            )

        # A readonly leaf cannot be written once it has a value, at any group
        # depth. Checked against the definition at the full path, not
        # `key in self._data`, which is never true for a dotted key (R20).
        if attr_def is not None and attr_def.readonly and self._has_field(key):
            raise ModelValidationError(
                f"Cannot modify readonly field '{key}'",
                field_name=key,
                field_value=value,
                validation_errors=[f"Field '{key}' is readonly and cannot be modified"],
            )

        # Null on an optional attribute means "no value": unset it rather than
        # store None, and let dependents recompute against the unset value.
        if value is None and attr_def is not None and attr_def.optional:
            self._unset_field(key, skip_derived_update)
            return

        # Validate the field if we have a definition. A templated range
        # ("0..{{ max_hp }}") is resolved against the current data first, as
        # validate() does; otherwise every write to it would fail as an
        # invalid range specification.
        if attr_def and validate_leaf:
            attr_def = self._resolve_templated_ranges({key: attr_def})[key]
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
            typed = self._model_typed_prefix(key)
            if typed is not None:
                # A write beneath a model-typed attribute -- possibly reached
                # through anonymous groups (R34) -- goes into that nested model,
                # so it validates and recomputes its own derived fields.
                prefix, prefix_def, rest = typed
                nested = self._nested_model_at(prefix, prefix_def)
                nested[rest] = value
                self._data = self._data.set(prefix, nested)
                self._derived_field_resolver.set_model_data_accessor(dict(self._data))
                if not skip_derived_update:
                    self._derived_field_resolver.set_field_value(prefix, nested)
                return
            data_copy = copy_on_write_set(dict(self._data), key, value)
            self._data = pmap(data_copy)
            self._derived_field_resolver.set_model_data_accessor(data_copy)
        else:
            # A model-typed attribute must hold a mapping or a model of that
            # type (R32). A mapping is built as the nested model, so its derived
            # fields compute and it validates (F57).
            if attr_def is not None and self._is_custom_model_type(attr_def.type):
                value = self._build_model_value(attr_def, value, key)
            elif attr_def is not None and attr_def.type == "list" and attr_def.of:
                # A list's model-typed elements are built (R33, D16).
                value = self._build_list_value(attr_def, value, key)
            self._data = self._data.set(key, value)
            self._derived_field_resolver.set_model_data_accessor(dict(self._data))

        # Update derived fields unless skipped
        if not skip_derived_update:
            self._derived_field_resolver.set_field_value(key, value)

    def _unset_field(self, key: str, skip_derived_update: bool = False) -> None:
        """Remove a field's value and update anything derived from it."""
        data_copy = copy_on_write_delete(dict(self._data), key)
        self._data = pmap(data_copy)
        self._derived_field_resolver.set_model_data_accessor(data_copy)
        if not skip_derived_update:
            self._derived_field_resolver.field_unset(key)

    def _declares(self, key: str) -> bool:
        """Whether ``key`` is a writable declared path.

        True when the definition exists (a leaf, a group leaf, or a
        model-typed attribute), or when the path's head is a model-typed
        attribute -- a path into a nested model is that model's business
        (R21, D6). ``type: dict`` attributes have no declared interior, so a
        dotted path through one is not declared.
        """
        if self.get_attribute_definition(key) is not None:
            return True
        if "." in key:
            return self._model_typed_prefix(key) is not None
        return False

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
        """Set a nested value, copying containers on the path (R14)."""
        data_copy = copy_on_write_set(dict(self._data), path, value)
        self._data = pmap(data_copy)
        self._derived_field_resolver.set_model_data_accessor(data_copy)

    def _has_nested_value(self, path: str) -> bool:
        """Check if a nested value exists using dot notation."""
        return has_nested_value(dict(self._data), path)

    def _delete_nested_value(self, path: str) -> None:
        """Delete a nested value, copying containers on the path (R14)."""
        if not self._has_nested_value(path):
            return
        data_copy = copy_on_write_delete(dict(self._data), path)
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

    def _resolve_templated_ranges(
        self, attributes: Dict[str, "AttributeDefinition"]
    ) -> Dict[str, "AttributeDefinition"]:
        """Resolve template expressions inside ``range`` constraints.

        A range may reference other attributes -- ``"0..{{ max_hp }}"`` -- which
        ``RangeValidator`` cannot parse, since it reads the bounds with
        ``float()``. Resolve those against the current model data here and hand
        the validator a concrete range, rather than teaching every validator
        about templating.

        This runs from :meth:`validate`, after derived fields have been
        computed, so a range may reference a derived attribute, and from
        :meth:`_set_with_validation` for the attribute being written.

        A range that fails to resolve is passed through unchanged. The
        validator then reports it as an invalid range specification, which is
        the correct loud failure -- never a skipped constraint.
        """
        resolved: Dict[str, AttributeDefinition] = {}
        context = None

        for name, attr_def in attributes.items():
            # Anonymous nested groups carry leaves that may have their own
            # templated ranges; recurse so they are resolved too.
            if attr_def.attributes:
                resolved[name] = attr_def.model_copy(
                    update={
                        "attributes": self._resolve_templated_ranges(
                            attr_def.attributes
                        )
                    }
                )
                continue

            range_spec = attr_def.range
            if not range_spec or not self._template_resolver.is_template(range_spec):
                resolved[name] = attr_def
                continue

            if context is None:
                context = self._build_validation_context()

            try:
                resolved_range = self._template_resolver.resolve_template(
                    range_spec, context
                )
            except Exception as exc:  # noqa: BLE001 - reported by the validator
                logger.debug(
                    f"Could not resolve range '{range_spec}' for '{name}': {exc}"
                )
                resolved[name] = attr_def
                continue

            resolved[name] = attr_def.model_copy(update={"range": str(resolved_range)})

        return resolved

    def _build_validation_context(self) -> Dict[str, Any]:
        """Build context for validation rule evaluation.

        The context is the model's data and nothing else. An unset optional
        attribute reads as None; stored data is untouched. (No instance-id key:
        an instance prefix is not part of the expression language, and adding
        one made ``{{ model.name }}`` resolve and then dropped ``model`` from
        dependency tracking.)
        """
        return unset_as_null(dict(self._data), self._resolved_attributes)

    def __eq__(self, other: Any) -> bool:
        """Test equality with another object."""
        if not isinstance(other, GrimoireModel):
            return False
        return self._model_def == other._model_def and dict(self._data) == dict(
            other._data
        )

    # A mutable mapping must not be hashable: its hash would change when it is
    # written, and today's hash already raises for any model holding a dict or
    # list (R23). Setting __hash__ to None makes it unhashable for every model.
    __hash__ = None  # type: ignore[assignment]


# Factory function for easy model creation
def create_model(
    model_definition: ModelDefinition,
    data: Optional[Dict[str, Any]] = None,
    template_resolver_type: str = "jinja2",
    template_resolver: Optional[TemplateResolver] = None,
    derived_field_resolver: Optional[DerivedFieldResolver] = None,
    instance_id: Optional[str] = None,
    skip_initial_validation: bool = False,
    template_resolver_kwargs: Optional[Dict[str, Any]] = None,
    derived_resolver_kwargs: Optional[Dict[str, Any]] = None,
    registry: Optional["ModelRegistry"] = None,
) -> GrimoireModel:
    """Factory function to create GrimoireModel instances.

    Args:
        model_definition: The model schema definition
        data: Initial model data
        template_resolver_type: Type of template resolver to use
        template_resolver: A pre-built template resolver (overrides the type)
        derived_field_resolver: A pre-built derived-field resolver
        instance_id: Unique identifier for this model instance
        skip_initial_validation: If True, do not validate on creation
        template_resolver_kwargs: Extra kwargs for the template resolver
        derived_resolver_kwargs: Extra kwargs for the derived-field resolver
        registry: Model registry for inheritance and type lookup (default:
            the global registry)

    Returns:
        Configured GrimoireModel instance

    Raises:
        TypeError: If an unknown keyword argument is passed.
    """
    if template_resolver is None:
        template_resolver = create_template_resolver(
            resolver_type=template_resolver_type,
            **(template_resolver_kwargs or {}),
        )

    if derived_field_resolver is None:
        derived_field_resolver = create_derived_field_resolver(
            template_resolver=template_resolver,
            **(derived_resolver_kwargs or {}),
        )

    return GrimoireModel(
        model_definition=model_definition,
        data=data,
        template_resolver=template_resolver,
        derived_field_resolver=derived_field_resolver,
        instance_id=instance_id,
        skip_initial_validation=skip_initial_validation,
        registry=registry,
    )


def create_model_without_validation(
    model_definition: ModelDefinition,
    data: Optional[Dict[str, Any]] = None,
    template_resolver_type: str = "jinja2",
    template_resolver: Optional[TemplateResolver] = None,
    derived_field_resolver: Optional[DerivedFieldResolver] = None,
    instance_id: Optional[str] = None,
    template_resolver_kwargs: Optional[Dict[str, Any]] = None,
    derived_resolver_kwargs: Optional[Dict[str, Any]] = None,
    registry: Optional["ModelRegistry"] = None,
) -> GrimoireModel:
    """Factory function to create GrimoireModel instances without validation.

    This allows incremental object building where validation happens later via
    explicit validate() calls.

    Args:
        model_definition: The model schema definition
        data: Initial model data (can be partial)
        template_resolver_type: Type of template resolver to use
        template_resolver: A pre-built template resolver (overrides the type)
        derived_field_resolver: A pre-built derived-field resolver
        instance_id: Unique identifier for this model instance
        template_resolver_kwargs: Extra kwargs for the template resolver
        derived_resolver_kwargs: Extra kwargs for the derived-field resolver
        registry: Model registry for inheritance and type lookup (default:
            the global registry)

    Returns:
        Configured GrimoireModel instance (unvalidated)

    Raises:
        TypeError: If an unknown keyword argument is passed.

    Note:
        - Required field validation is skipped
        - Derived fields are still computed from available data
        - Call validate() explicitly when object is complete

    Example:
        >>> character_def = ModelDefinition(
        ...     id="character",
        ...     attributes={
        ...         "name": {"type": "str"},
        ...         "level": {"type": "int"},
        ...     }
        ... )
        >>> character = create_model_without_validation(
        ...     character_def, {"name": "Hero"}
        ... )
        >>> character["level"] = 5
        >>> errors = character.validate()
    """
    if template_resolver is None:
        template_resolver = create_template_resolver(
            resolver_type=template_resolver_type,
            **(template_resolver_kwargs or {}),
        )

    if derived_field_resolver is None:
        derived_field_resolver = create_derived_field_resolver(
            template_resolver=template_resolver,
            **(derived_resolver_kwargs or {}),
        )

    return GrimoireModel(
        model_definition=model_definition,
        data=data,
        template_resolver=template_resolver,
        derived_field_resolver=derived_field_resolver,
        instance_id=instance_id,
        skip_initial_validation=True,
        registry=registry,
    )
