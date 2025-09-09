"""
Wyrdbound Model Package

A dict-like model system with schema validation, derived fields, and inheritance
designed for integration with wyrdbound-context.

Key Features:
- Dict-like interface (MutableMapping) 
- Schema validation with Pydantic
- Reactive derived fields with dependency tracking
- Model inheritance support
- Template-based field expressions using Jinja2
- Immutable operations with pyrsistent
- Dependency injection for extensibility

Example Usage:
    from wyrdbound_model import WyrdboundModel, ModelDefinition, create_model
    
    # Define model schema
    character_def = ModelDefinition(
        id="character",
        name="Player Character",
        attributes={
            "name": {"type": "str", "required": True},
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
    
    # Works with wyrdbound-context
    from wyrdbound_context import WyrdboundContext
    context = WyrdboundContext({'character': character})
    context.set_variable('character.level', 7)
"""

__version__ = "0.1.0"
__author__ = "The Wyrd One"
__email__ = "wyrdbound@proton.me"

# Core exports
from .core.model import (
    WyrdboundModel,
    create_model,
)

from .core.schema import (
    ModelDefinition,
    AttributeDefinition,
    ValidationRule,
)

from .core.exceptions import (
    WyrdboundModelError,
    ModelValidationError,
    TemplateResolutionError,
    InheritanceError,
    DependencyError,
    ConfigurationError,
)

# Resolver exports  
from .resolvers.template import (
    TemplateResolver,
    Jinja2TemplateResolver,
    ModelContextTemplateResolver,
    CachingTemplateResolver,
    create_template_resolver,
)

from .resolvers.derived import (
    DerivedFieldResolver,
    BatchedDerivedFieldResolver,
    ObservableValue,
    DependencyInfo,
    create_derived_field_resolver,
)

# Utility exports
from .utils.inheritance import resolve_model_inheritance
from .utils.paths import (
    get_nested_value,
    set_nested_value,
    has_nested_value,
    delete_nested_value,
    flatten_dict,
    unflatten_dict,
)

# Validation exports
from .validation.validators import (
    TypeValidator,
    RangeValidator,
    EnumValidator,
    RequiredValidator,
    PatternValidator,
    LengthValidator,
    ValidationEngine,
    validate_field_value,
    validate_model_data,
    get_validation_engine,
)

__all__ = [
    # Core classes
    "WyrdboundModel",
    "ModelDefinition", 
    "AttributeDefinition",
    "ValidationRule",
    
    # Factory functions
    "create_model",
    "create_template_resolver",
    "create_derived_field_resolver",
    
    # Exceptions
    "WyrdboundModelError",
    "ModelValidationError", 
    "TemplateResolutionError",
    "InheritanceError",
    "DependencyError",
    "ConfigurationError",
    
    # Resolvers
    "TemplateResolver",
    "Jinja2TemplateResolver",
    "ModelContextTemplateResolver", 
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

# Package metadata
__pkg_info__ = {
    "name": "wyrdbound-model",
    "version": __version__,
    "description": "Dict-like model system with validation and derived fields for Wyrdbound",
    "long_description": __doc__,
    "author": __author__,
    "author_email": __email__,
    "license": "Proprietary",
    "url": "https://github.com/wyrdbound/wyrdbound-model",
    "classifiers": [
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: Other/Proprietary License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9", 
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Games/Entertainment :: Role-Playing",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    "keywords": "gaming rpg tabletop model validation schema",
    "python_requires": ">=3.8",
    "install_requires": [
        "pydantic>=2.0.0",
        "pyrsistent>=0.19.0", 
        "jinja2>=3.1.0",
        "pyyaml>=6.0",
    ],
    "extras_require": {
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "ruff>=0.1.0",
            "mypy>=1.0.0",
            "black>=22.0.0",
        ],
        "docs": [
            "sphinx>=4.0.0",
            "sphinx-rtd-theme>=1.0.0",
            "sphinxcontrib-napoleon>=0.7",
        ],
        "test": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0", 
            "pytest-mock>=3.0.0",
            "hypothesis>=6.0.0",
        ],
    },
}

# Integration helpers for wyrdbound-context
def register_with_wyrdbound_context():
    """Register WyrdboundModel as a compatible value type with wyrdbound-context.
    
    This function should be called if you want seamless integration between
    wyrdbound-model and wyrdbound-context packages.
    """
    try:
        from wyrdbound_context import WyrdboundContext
        
        # Register our model as a compatible dict-like type
        if hasattr(WyrdboundContext, 'register_dict_like_type'):
            WyrdboundContext.register_dict_like_type(WyrdboundModel)  # type: ignore
        
        return True
    except ImportError:
        # wyrdbound-context not available
        return False

# Optional auto-registration
try:
    # Try to register automatically if wyrdbound-context is available
    register_with_wyrdbound_context()
except Exception:
    # Silently ignore registration failures
    pass
