"""
Grimoire Model Package

A dict-like model system with schema validation, derived fields, and inheritance
designed for integration with grimoire-context.

Key Features:
- Dict-like interface (MutableMapping)
- Schema validation with Pydantic
- Reactive derived fields with dependency tracking
- Model inheritance support
- Template-based field expressions using Jinja2
- Immutable operations with pyrsistent
- Dependency injection for extensibility

Example Usage:
    from grimoire_model import GrimoireModel, ModelDefinition, create_model

    # Define model schema
    character_def = ModelDefinition(
        id="character",
        name="Player Character",
        attributes={
            "name": {"type": "str"},
            "level": {"type": "int", "default": 1},
            "hp": {"type": "int", "default": 8},
            "max_hp": {"type": "int", "derived": "{{ level * 8 }}"}
        }
    )

    # Create model instance
    character = create_model(character_def, {"name": "Aragorn", "level": 5})

    # Use as dict
    character['level'] = 6  # Automatically updates max_hp derived field
    print(character['max_hp'])  # 48

    # Works with grimoire-context
    from grimoire_context import GrimoireContext
    context = GrimoireContext({'character': character})
    context.set_variable('character.level', 7)
"""

__version__ = "0.8.1"
__author__ = "The Wyrd One"
__email__ = "wyrdbound@proton.me"

# Core exports
from .core.exceptions import (
    ConfigurationError,
    DependencyError,
    GrimoireModelError,
    InheritanceError,
    ModelValidationError,
    TemplateResolutionError,
)
from .core.model import (
    GrimoireModel,
    create_model,
    create_model_without_validation,
)
from .core.primitive_registry import (
    PrimitiveTypeRegistry,
    clear_primitive_registry,
    get_default_primitive_registry,
    is_primitive_type,
    register_primitive_type,
    unregister_primitive_type,
)
from .core.registry import (
    ModelRegistry,
    clear_registry,
    get_default_registry,
    get_model,
    get_model_registry,  # Kept for backward compatibility
    register_model,
)
from .core.schema import (
    AttributeDefinition,
    ModelDefinition,
    ValidationRule,
    iter_leaf_attributes,
    unset_as_null,
)

# Logging configuration
from .logging import clear_logger_injection, get_logger, inject_logger, logger
from .resolvers.derived import (
    BatchedDerivedFieldResolver,
    DependencyInfo,
    DerivedFieldResolver,
    ObservableValue,
    create_derived_field_resolver,
)

# Resolver exports
from .resolvers.template import (
    CachingTemplateResolver,
    Jinja2TemplateResolver,
    TemplateResolver,
    create_template_resolver,
)

# Utility exports
from .utils.inheritance import resolve_model_inheritance
from .utils.paths import (
    delete_nested_value,
    flatten_dict,
    get_nested_value,
    has_nested_value,
    set_nested_value,
    unflatten_dict,
)

# Validation exports
from .validation.validators import (
    EnumValidator,
    LengthValidator,
    PatternValidator,
    RangeValidator,
    RequiredValidator,
    TypeValidator,
    ValidationEngine,
    get_validation_engine,
    validate_field_value,
    validate_model_data,
)

__all__ = [
    "iter_leaf_attributes",
    "unset_as_null",
    # Core classes
    "GrimoireModel",
    "ModelDefinition",
    "AttributeDefinition",
    "ValidationRule",
    # Factory functions
    "create_model",
    "create_model_without_validation",
    "create_template_resolver",
    "create_derived_field_resolver",
    # Registry
    "ModelRegistry",
    "get_default_registry",
    "get_model_registry",  # Backward compatibility
    "clear_registry",
    "register_model",
    "get_model",
    # Primitive Type Registry
    "PrimitiveTypeRegistry",
    "register_primitive_type",
    "unregister_primitive_type",
    "is_primitive_type",
    "get_default_primitive_registry",
    "clear_primitive_registry",
    # Logging
    "logger",
    "get_logger",
    "inject_logger",
    "clear_logger_injection",
    # Exceptions
    "GrimoireModelError",
    "ModelValidationError",
    "TemplateResolutionError",
    "InheritanceError",
    "DependencyError",
    "ConfigurationError",
    # Resolvers
    "TemplateResolver",
    "Jinja2TemplateResolver",
    "CachingTemplateResolver",
    "DerivedFieldResolver",
    "BatchedDerivedFieldResolver",
    "ObservableValue",
    "DependencyInfo",
    # Utilities
    "resolve_model_inheritance",
    "get_nested_value",
    "set_nested_value",
    "has_nested_value",
    "delete_nested_value",
    "flatten_dict",
    "unflatten_dict",
    # Validators
    "TypeValidator",
    "RangeValidator",
    "EnumValidator",
    "RequiredValidator",
    "PatternValidator",
    "LengthValidator",
    "ValidationEngine",
    "validate_field_value",
    "validate_model_data",
    "get_validation_engine",
]
