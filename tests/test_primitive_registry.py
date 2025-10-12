"""
Tests for the primitive type registry functionality.
"""

import pytest

from grimoire_model import (
    AttributeDefinition,
    ModelDefinition,
    PrimitiveTypeRegistry,
    clear_primitive_registry,
    create_model_without_validation,
    get_default_primitive_registry,
    is_primitive_type,
    register_primitive_type,
    unregister_primitive_type,
)
from grimoire_model.core.exceptions import ModelValidationError


class TestPrimitiveTypeRegistry:
    """Test PrimitiveTypeRegistry class."""

    def setup_method(self):
        """Clear registry before each test."""
        clear_primitive_registry()

    def teardown_method(self):
        """Clear registry after each test."""
        clear_primitive_registry()

    def test_registry_initialization(self):
        """Test that a registry can be created."""
        registry = PrimitiveTypeRegistry()
        assert len(registry) == 0
        assert registry.list_registered_types() == []

    def test_register_primitive_type(self):
        """Test registering a custom primitive type."""
        registry = PrimitiveTypeRegistry()
        registry.register("roll")

        assert registry.is_registered("roll")
        assert "roll" in registry
        assert len(registry) == 1
        assert "roll" in registry.list_registered_types()

    def test_register_multiple_types(self):
        """Test registering multiple primitive types."""
        registry = PrimitiveTypeRegistry()
        registry.register("roll")
        registry.register("duration")
        registry.register("distance")

        assert len(registry) == 3
        assert registry.is_registered("roll")
        assert registry.is_registered("duration")
        assert registry.is_registered("distance")

        types = registry.list_registered_types()
        assert "roll" in types
        assert "duration" in types
        assert "distance" in types

    def test_register_with_validator(self):
        """Test registering a type with a validator function."""

        def validate_roll(value):
            if isinstance(value, str) and "d" in value:
                return True, None
            return False, "Invalid dice roll format"

        registry = PrimitiveTypeRegistry()
        registry.register("roll", validator=validate_roll)

        assert registry.is_registered("roll")
        validator = registry.get_validator("roll")
        assert validator is not None
        assert validator == validate_roll

    def test_unregister_type(self):
        """Test unregistering a primitive type."""
        registry = PrimitiveTypeRegistry()
        registry.register("roll")

        assert registry.is_registered("roll")
        result = registry.unregister("roll")

        assert result is True
        assert not registry.is_registered("roll")
        assert len(registry) == 0

    def test_unregister_nonexistent_type(self):
        """Test unregistering a type that doesn't exist."""
        registry = PrimitiveTypeRegistry()
        result = registry.unregister("nonexistent")
        assert result is False

    def test_cannot_register_builtin_primitive(self):
        """Test that built-in primitives cannot be registered."""
        registry = PrimitiveTypeRegistry()

        with pytest.raises(ValueError, match="built-in primitive type"):
            registry.register("str")

        with pytest.raises(ValueError, match="built-in primitive type"):
            registry.register("int")

        with pytest.raises(ValueError, match="built-in primitive type"):
            registry.register("float")

    def test_register_empty_type_name(self):
        """Test that empty type names cannot be registered."""
        registry = PrimitiveTypeRegistry()

        with pytest.raises(ValueError, match="non-empty string"):
            registry.register("")

    def test_overwrite_registration_warning(self, caplog):
        """Test that overwriting a registration logs a warning."""
        registry = PrimitiveTypeRegistry()

        def validator1(value):
            return True, None

        def validator2(value):
            return False, "Error"

        registry.register("roll", validator=validator1)
        registry.register("roll", validator=validator2)

        # Should have logged a warning
        assert "already registered" in caplog.text.lower()

        # Should use the new validator
        assert registry.get_validator("roll") == validator2

    def test_clear_registry(self):
        """Test clearing all registered types."""
        registry = PrimitiveTypeRegistry()
        registry.register("roll")
        registry.register("duration")
        registry.register("distance")

        assert len(registry) == 3

        count = registry.clear()

        assert count == 3
        assert len(registry) == 0
        assert registry.list_registered_types() == []

    def test_registry_repr(self):
        """Test string representation of the registry."""
        registry = PrimitiveTypeRegistry()
        registry.register("roll")
        registry.register("duration")

        repr_str = repr(registry)
        assert "PrimitiveTypeRegistry" in repr_str
        assert "2 types" in repr_str
        assert "roll" in repr_str
        assert "duration" in repr_str


class TestGlobalPrimitiveRegistry:
    """Test global primitive registry convenience functions."""

    def setup_method(self):
        """Clear registry before each test."""
        clear_primitive_registry()

    def teardown_method(self):
        """Clear registry after each test."""
        clear_primitive_registry()

    def test_get_default_registry_singleton(self):
        """Test that the default registry is a singleton."""
        registry1 = get_default_primitive_registry()
        registry2 = get_default_primitive_registry()
        assert registry1 is registry2

    def test_register_primitive_type_function(self):
        """Test register_primitive_type convenience function."""
        register_primitive_type("roll")

        assert is_primitive_type("roll")
        assert not is_primitive_type("nonexistent")

    def test_unregister_primitive_type_function(self):
        """Test unregister_primitive_type convenience function."""
        register_primitive_type("roll")
        assert is_primitive_type("roll")

        result = unregister_primitive_type("roll")
        assert result is True
        assert not is_primitive_type("roll")

    def test_clear_primitive_registry_function(self):
        """Test clear_primitive_registry convenience function."""
        register_primitive_type("roll")
        register_primitive_type("duration")

        count = clear_primitive_registry()
        assert count == 2
        assert not is_primitive_type("roll")
        assert not is_primitive_type("duration")


class TestPrimitiveTypeIntegration:
    """Test integration of primitive types with GrimoireModel."""

    def setup_method(self):
        """Clear registry before each test."""
        clear_primitive_registry()

    def teardown_method(self):
        """Clear registry after each test."""
        clear_primitive_registry()

    def test_custom_primitive_in_model(self):
        """Test using a registered custom primitive type in a model."""
        # Register 'roll' as a primitive type
        register_primitive_type("roll")

        # Define a model with the custom primitive type
        weapon_attrs = {
            "name": AttributeDefinition(type="str", required=True),
            "damage": AttributeDefinition(type="roll", required=True),
        }

        weapon_def = ModelDefinition(
            id="weapon",
            name="Weapon",
            kind="model",
            description="Weapon model",
            version=1,
            attributes=weapon_attrs,
        )

        # Create a model instance with the custom primitive
        weapon_data = {"model": "weapon", "name": "Dagger", "damage": "1d4"}

        weapon = create_model_without_validation(weapon_def, weapon_data)

        # Verify the data was stored as-is (primitive behavior)
        assert weapon["name"] == "Dagger"
        assert weapon["damage"] == "1d4"
        assert isinstance(weapon["damage"], str)

    def test_unregistered_type_treated_as_model(self):
        """Test that unregistered types are still treated as custom models."""
        # Don't register 'roll' - it should be treated as a custom model

        weapon_attrs = {
            "name": AttributeDefinition(type="str", required=True),
            "damage": AttributeDefinition(type="roll", required=True),
        }

        weapon_def = ModelDefinition(
            id="weapon",
            name="Weapon",
            kind="model",
            description="Weapon model",
            version=1,
            attributes=weapon_attrs,
        )

        weapon_data = {"model": "weapon", "name": "Dagger", "damage": "1d4"}

        # This should fail because 'roll' is not registered as a model
        with pytest.raises(ModelValidationError, match="Invalid model type 'roll'"):
            create_model_without_validation(weapon_def, weapon_data)

    def test_multiple_custom_primitives(self):
        """Test using multiple custom primitive types in a model."""
        # Register multiple custom primitives
        register_primitive_type("roll")
        register_primitive_type("duration")
        register_primitive_type("distance")

        spell_attrs = {
            "name": AttributeDefinition(type="str", required=True),
            "damage": AttributeDefinition(type="roll"),
            "duration": AttributeDefinition(type="duration"),
            "range": AttributeDefinition(type="distance"),
        }

        spell_def = ModelDefinition(
            id="spell",
            name="Spell",
            kind="model",
            description="Spell model",
            version=1,
            attributes=spell_attrs,
        )

        spell_data = {
            "model": "spell",
            "name": "Fireball",
            "damage": "8d6",
            "duration": "instant",
            "range": "150 feet",
        }

        spell = create_model_without_validation(spell_def, spell_data)

        assert spell["name"] == "Fireball"
        assert spell["damage"] == "8d6"
        assert spell["duration"] == "instant"
        assert spell["range"] == "150 feet"

    def test_builtin_primitives_still_work(self):
        """Test that built-in primitives continue to work normally."""
        register_primitive_type("roll")

        character_attrs = {
            "name": AttributeDefinition(type="str", required=True),
            "level": AttributeDefinition(type="int", default=1),
            "hp": AttributeDefinition(type="float", default=10.0),
            "active": AttributeDefinition(type="bool", default=True),
            "damage": AttributeDefinition(type="roll"),
        }

        character_def = ModelDefinition(
            id="character",
            name="Character",
            kind="model",
            description="Character model",
            version=1,
            attributes=character_attrs,
        )

        character_data = {
            "model": "character",
            "name": "Hero",
            "level": 5,
            "hp": 50.5,
            "active": True,
            "damage": "1d6",
        }

        character = create_model_without_validation(character_def, character_data)

        assert character["name"] == "Hero"
        assert character["level"] == 5
        assert character["hp"] == 50.5
        assert character["active"] is True
        assert character["damage"] == "1d6"

    def test_primitive_type_in_derived_field(self):
        """Test that custom primitives work in derived field templates."""
        register_primitive_type("roll")

        weapon_attrs = {
            "name": AttributeDefinition(type="str", required=True),
            "base_damage": AttributeDefinition(type="roll", required=True),
            "bonus": AttributeDefinition(type="int", default=0),
            "description": AttributeDefinition(
                type="str", derived="{{ name }} deals {{ base_damage }} + {{ bonus }}"
            ),
        }

        weapon_def = ModelDefinition(
            id="weapon",
            name="Weapon",
            kind="model",
            description="Weapon model",
            version=1,
            attributes=weapon_attrs,
        )

        weapon_data = {
            "model": "weapon",
            "name": "Longsword",
            "base_damage": "1d8",
            "bonus": 2,
        }

        weapon = create_model_without_validation(weapon_def, weapon_data)

        assert weapon["base_damage"] == "1d8"
        assert weapon["description"] == "Longsword deals 1d8 + 2"

    def test_reproduction_code_from_issue(self):
        """Test the exact reproduction code from the issue."""
        # Register 'roll' as a primitive type (the fix)
        register_primitive_type("roll")

        # Define a model with a custom primitive type that should work like 'str'
        weapon_attrs = {
            "name": AttributeDefinition(type="str", required=True),
            "damage": AttributeDefinition(type="roll", required=True),
        }

        weapon_def = ModelDefinition(
            id="weapon",
            name="Weapon",
            kind="model",
            description="Weapon model",
            version=1,
            attributes=weapon_attrs,
        )

        # Data with dice roll notation (should be stored as string)
        weapon_data = {"model": "weapon", "name": "Dagger", "damage": "1d4"}

        # This should now succeed
        weapon_obj = create_model_without_validation(weapon_def, weapon_data)
        assert weapon_obj.get("damage") == "1d4"
        assert weapon_obj.get("name") == "Dagger"


class TestThreadSafety:
    """Test thread safety of the primitive type registry."""

    def setup_method(self):
        """Clear registry before each test."""
        clear_primitive_registry()

    def teardown_method(self):
        """Clear registry after each test."""
        clear_primitive_registry()

    def test_concurrent_registration(self):
        """Test that concurrent registration is thread-safe."""
        import threading

        def register_types(start_index):
            for i in range(start_index, start_index + 10):
                register_primitive_type(f"type_{i}")

        threads = []
        for i in range(5):
            t = threading.Thread(target=register_types, args=(i * 10,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Should have registered 50 types (5 threads * 10 types each)
        registry = get_default_primitive_registry()
        assert len(registry) == 50

    def test_concurrent_read_write(self):
        """Test concurrent reading and writing."""
        import threading

        register_primitive_type("test_type")

        def reader():
            for _ in range(100):
                is_primitive_type("test_type")

        def writer():
            for i in range(100):
                register_primitive_type(f"type_{i}")

        threads = []
        for _ in range(3):
            threads.append(threading.Thread(target=reader))
            threads.append(threading.Thread(target=writer))

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # All operations should complete without error
        registry = get_default_primitive_registry()
        assert registry.is_registered("test_type")
