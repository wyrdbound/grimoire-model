"""
Core schema definitions for grimoire-model package.

Provides Pydantic-based model and attribute definitions that follow the GRIMOIRE
specification for tabletop gaming model schemas.
"""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

from .exceptions import ConfigurationError


class ValidationRule(BaseModel):
    """Model validation rule definition.

    Defines a validation rule that can be applied to model instances to ensure
    data consistency and business rule compliance.
    """

    expression: str = Field(
        ..., description="Template expression that must evaluate to True"
    )
    message: str = Field(
        ..., description="Error message to display when validation fails"
    )
    fields: List[str] = Field(
        default_factory=list,
        description="List of fields this validation depends on",
    )
    severity: str = Field(
        default="error",
        description="Severity level: 'error', 'warning', or 'info'",
    )

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        """Validate severity is one of allowed values."""
        allowed = {"error", "warning", "info"}
        if v not in allowed:
            raise ValueError(f"Severity must be one of {allowed}, got '{v}'")
        return v

    @field_validator("expression")
    @classmethod
    def validate_expression(cls, v: str) -> str:
        """Validate expression is not empty."""
        if not v.strip():
            raise ValueError("Validation expression cannot be empty")
        return v.strip()


class AttributeDefinition(BaseModel):
    """Definition of a model attribute.

    Defines the schema for a single attribute within a model, including type
    information, constraints, default values, and derived field expressions.
    """

    type: str = Field(
        ...,
        description="Attribute type: int, str, float, bool, list, dict, or model ID",
    )
    default: Any = Field(default=None, description="Default value for the attribute")
    required: bool = Field(
        default=True, description="Whether the attribute is required"
    )
    derived: Optional[str] = Field(
        default=None,
        description="Template expression for derived attributes",
    )
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description of the attribute",
    )

    # Validation constraints
    range: Optional[str] = Field(
        default=None,
        description="Value range constraint (e.g., '1..20', '1..', '..100')",
    )
    enum: Optional[List[str]] = Field(
        default=None,
        description="List of allowed values",
    )
    of: Optional[str] = Field(
        default=None,
        description="Element type for list/dict attributes",
    )
    pattern: Optional[str] = Field(
        default=None,
        description="Regex pattern for string validation",
    )

    # Additional flags
    optional: Optional[bool] = Field(
        default=None,
        description="Whether attribute can be null/undefined (overrides required)",
    )
    readonly: bool = Field(
        default=False,
        description="Whether attribute is read-only after creation",
    )
    computed: bool = Field(
        default=False,
        description="Whether attribute is computed/derived",
    )

    def model_post_init(self, __context: Any) -> None:
        """Post-initialization processing."""
        super().model_post_init(__context)

        # Set computed flag for derived attributes
        if self.derived is not None:
            self.computed = True

        # Handle optional override of required
        if self.optional is not None:
            self.required = not self.optional

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Validate attribute type."""
        basic_types = {"int", "str", "float", "bool", "list", "dict", "any"}
        if v not in basic_types and not v.replace("_", "").replace("-", "").isalnum():
            # Allow model IDs (alphanumeric with underscores/hyphens)
            raise ValueError(
                f"Invalid type '{v}': must be basic type or valid model ID"
            )
        return v

    @field_validator("range")
    @classmethod
    def validate_range(cls, v: Optional[str]) -> Optional[str]:
        """Validate range constraint format."""
        if v is None:
            return v

        # Basic validation for range format
        if not any(pattern in v for pattern in ["..", ">=", "<=", ">", "<", "="]):
            raise ValueError(
                f"Invalid range format '{v}': must contain comparison operators"
            )

        return v

    @model_validator(mode="after")
    def validate_computed_attributes(self) -> "AttributeDefinition":
        """Validate computed/derived attribute constraints."""
        if self.computed and self.derived is None:
            raise ValueError("Computed attributes must have a derived expression")

        if self.derived is not None and not self.computed:
            # Auto-set computed for derived fields
            self.computed = True

        if self.readonly and self.default is None and not self.computed:
            raise ValueError(
                "Readonly attributes must have a default value or be computed"
            )

        return self


class ModelDefinition(BaseModel):
    """Complete model definition following GRIMOIRE specification.

    Defines a complete model schema including metadata, inheritance relationships,
    attributes, and validation rules. Automatically registers itself in the global
    model registry upon creation.
    """

    id: str = Field(..., description="Unique model identifier")
    name: str = Field(..., description="Human-readable model name")
    kind: str = Field(default="model", description="Model kind/type")
    description: Optional[str] = Field(default=None, description="Model description")
    version: int = Field(default=1, description="Model schema version")
    namespace: str = Field(
        default="default", description="Model namespace for registry organization"
    )

    # Inheritance
    extends: List[str] = Field(
        default_factory=list,
        description="List of parent model IDs to inherit from",
    )

    # Attributes
    attributes: Dict[str, AttributeDefinition] = Field(
        default_factory=dict,
        description="Model attributes definition",
    )

    @field_validator("attributes", mode="before")
    @classmethod
    def validate_attributes(cls, v: Any) -> Dict[str, Any]:
        """Validate and convert attribute definitions."""
        if not isinstance(v, dict):
            return v

        converted_attributes = {}
        for key, value in v.items():
            if isinstance(value, dict):
                try:
                    # Try to create AttributeDefinition to validate
                    AttributeDefinition(**value)
                    converted_attributes[key] = value
                except Exception as e:
                    raise ConfigurationError(
                        f"Invalid attribute definition for '{key}': {e}",
                        config_key=key,
                        config_value=value,
                    ) from e
            else:
                converted_attributes[key] = value

        return converted_attributes

    # Validation
    validations: List[ValidationRule] = Field(
        default_factory=list,
        description="Model validation rules",
    )

    # Metadata
    tags: List[str] = Field(
        default_factory=list,
        description="Model tags for categorization",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
    )

    def model_post_init(self, __context: Any) -> None:
        """Register model after validation."""
        super().model_post_init(__context)

        # Register this model in the global registry
        from .registry import register_model

        register_model(self.namespace, self)

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        """Validate model ID format."""
        if not v:
            raise ValueError("Model ID cannot be empty")

        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError(
                "Model ID must contain only alphanumeric characters, "
                "underscores, and hyphens"
            )

        return v

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, v: str) -> str:
        """Validate model kind."""
        allowed_kinds = {"model", "entity", "component", "system", "enum", "interface"}
        if v not in allowed_kinds:
            # Allow custom kinds but validate format
            if not v.replace("_", "").replace("-", "").isalnum():
                raise ValueError(
                    "Model kind must be alphanumeric with underscores/hyphens"
                )

        return v

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: int) -> int:
        """Validate version number."""
        if v < 1:
            raise ValueError("Version must be a positive integer")
        return v

    @field_validator("namespace")
    @classmethod
    def validate_namespace(cls, v: str) -> str:
        """Validate namespace format."""
        if not v:
            raise ValueError("Namespace cannot be empty")

        if not v.replace("_", "").replace("-", "").replace(".", "").isalnum():
            raise ValueError(
                "Namespace must contain only alphanumeric characters, "
                "underscores, hyphens, and dots"
            )

        return v

    @model_validator(mode="after")
    def validate_inheritance_chain(self) -> "ModelDefinition":
        """Validate inheritance doesn't reference self."""
        if self.id in self.extends:
            raise ValueError(f"Model '{self.id}' cannot extend itself")

        # Check for duplicate parents
        if len(self.extends) != len(set(self.extends)):
            duplicates = [
                parent for parent in self.extends if self.extends.count(parent) > 1
            ]
            raise ValueError(f"Duplicate parent models: {duplicates}")

        return self

    def get_attribute(self, name: str) -> Optional[AttributeDefinition]:
        """Get attribute definition by name."""
        attr = self.attributes.get(name)
        if isinstance(attr, AttributeDefinition):
            return attr
        return None

    def get_required_attributes(self) -> Dict[str, AttributeDefinition]:
        """Get all required attributes."""
        return {
            name: attr
            for name, attr in self.attributes.items()
            if isinstance(attr, AttributeDefinition)
            and attr.required
            and not attr.computed
        }

    def get_derived_attributes(self) -> Dict[str, AttributeDefinition]:
        """Get all derived/computed attributes."""
        return {
            name: attr
            for name, attr in self.attributes.items()
            if isinstance(attr, AttributeDefinition) and attr.computed
        }

    def get_validation_rules(self) -> List[ValidationRule]:
        """Get all validation rules for this model."""
        return self.validations

    def has_inheritance(self) -> bool:
        """Check if model has parent models."""
        return len(self.extends) > 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = self.model_dump()

        # Convert AttributeDefinition objects back to dicts
        result["attributes"] = {
            name: attr.model_dump() if isinstance(attr, AttributeDefinition) else attr
            for name, attr in self.attributes.items()
        }

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelDefinition":
        """Create ModelDefinition from dictionary."""
        return cls(**data)


# Type aliases for convenience
AttributeDict = Dict[str, Union[AttributeDefinition, Dict[str, Any]]]
ModelRegistry = Dict[str, ModelDefinition]
