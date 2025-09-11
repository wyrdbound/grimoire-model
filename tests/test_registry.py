"""
Tests for the ModelRegistry functionality.
"""

import pytest

from grimoire_model import (
    AttributeDefinition,
    ModelDefinition,
    ModelRegistry,
    clear_registry,
    get_default_registry,
    get_model,
    get_model_registry,
    register_model,
)


class TestModelRegistry:
    """Test ModelRegistry functionality."""

    def setup_method(self):
        """Clear registry before each test."""
        clear_registry()

    def teardown_method(self):
        """Clear registry after each test."""
        clear_registry()

    def test_registry_singleton(self):
        """Test that the default registry is a singleton."""
        registry1 = get_model_registry()
        registry2 = get_model_registry()
        registry3 = get_default_registry()
        assert registry1 is registry2
        assert registry1 is registry3

    def test_register_and_get_model(self):
        """Test basic register and get operations."""
        registry = ModelRegistry()

        model_def = ModelDefinition(
            id="test_model",
            name="Test Model",
            namespace="test",
            attributes={"name": AttributeDefinition(type="str", required=True)},
        )

        # Register the model
        registry.register("test", "test_model", model_def)

        # Get the model
        retrieved = registry.get("test", "test_model")
        assert retrieved is model_def

        # Get by key
        retrieved_by_key = registry.get_by_key("test__test_model")
        assert retrieved_by_key is model_def

    def test_has_model(self):
        """Test checking if models exist."""
        registry = ModelRegistry()

        model_def = ModelDefinition(
            id="test_model", name="Test Model", namespace="test", attributes={}
        )

        # Should not exist initially
        assert not registry.has("test", "test_model")
        assert not registry.has_key("test__test_model")

        # Register and check again
        registry.register("test", "test_model", model_def)
        assert registry.has("test", "test_model")
        assert registry.has_key("test__test_model")

    def test_unregister_model(self):
        """Test removing models from registry."""
        registry = ModelRegistry()

        model_def = ModelDefinition(
            id="test_model", name="Test Model", namespace="test", attributes={}
        )

        # Register the model
        registry.register("test", "test_model", model_def)
        assert registry.has("test", "test_model")

        # Unregister the model
        result = registry.unregister("test", "test_model")
        assert result is True
        assert not registry.has("test", "test_model")

        # Try to unregister again
        result = registry.unregister("test", "test_model")
        assert result is False

    def test_list_models(self):
        """Test listing models in registry."""
        registry = ModelRegistry()

        model1 = ModelDefinition(
            id="model1", name="Model 1", namespace="test", attributes={}
        )
        model2 = ModelDefinition(
            id="model2", name="Model 2", namespace="test", attributes={}
        )
        model3 = ModelDefinition(
            id="model3", name="Model 3", namespace="other", attributes={}
        )

        registry.register("test", "model1", model1)
        registry.register("test", "model2", model2)
        registry.register("other", "model3", model3)

        # List all models
        all_models = registry.list_models()
        assert len(all_models) == 3
        assert "test__model1" in all_models
        assert "test__model2" in all_models
        assert "other__model3" in all_models

        # List models in specific namespace
        test_models = registry.list_models("test")
        assert len(test_models) == 2
        assert "test__model1" in test_models
        assert "test__model2" in test_models
        assert "other__model3" not in test_models

    def test_list_namespaces(self):
        """Test listing namespaces."""
        registry = ModelRegistry()

        model1 = ModelDefinition(
            id="model1", name="Model 1", namespace="test", attributes={}
        )
        model2 = ModelDefinition(
            id="model2", name="Model 2", namespace="other", attributes={}
        )

        registry.register("test", "model1", model1)
        registry.register("other", "model2", model2)

        namespaces = registry.list_namespaces()
        assert len(namespaces) == 2
        assert "test" in namespaces
        assert "other" in namespaces

    def test_clear_namespace(self):
        """Test clearing a specific namespace."""
        registry = ModelRegistry()

        model1 = ModelDefinition(
            id="model1", name="Model 1", namespace="test", attributes={}
        )
        model2 = ModelDefinition(
            id="model2", name="Model 2", namespace="test", attributes={}
        )
        model3 = ModelDefinition(
            id="model3", name="Model 3", namespace="other", attributes={}
        )

        registry.register("test", "model1", model1)
        registry.register("test", "model2", model2)
        registry.register("other", "model3", model3)

        # Clear test namespace
        count = registry.clear_namespace("test")
        assert count == 2
        assert not registry.has("test", "model1")
        assert not registry.has("test", "model2")
        assert registry.has("other", "model3")  # Should still exist

    def test_clear_all(self):
        """Test clearing all models from registry."""
        registry = ModelRegistry()

        model1 = ModelDefinition(
            id="model1", name="Model 1", namespace="test", attributes={}
        )
        model2 = ModelDefinition(
            id="model2", name="Model 2", namespace="other", attributes={}
        )

        registry.register("test", "model1", model1)
        registry.register("other", "model2", model2)

        # Clear all models
        count = registry.clear_all()
        assert count == 2
        assert len(registry) == 0
        assert len(registry.list_namespaces()) == 0

    def test_get_registry_dict(self):
        """Test getting dictionary representation."""
        registry = ModelRegistry()

        model1 = ModelDefinition(
            id="model1", name="Model 1", namespace="test", attributes={}
        )
        model2 = ModelDefinition(
            id="model2", name="Model 2", namespace="other", attributes={}
        )

        registry.register("test", "model1", model1)
        registry.register("other", "model2", model2)

        # Get all models as dict
        all_dict = registry.get_registry_dict()
        assert len(all_dict) == 2
        assert "test__model1" in all_dict
        assert "other__model2" in all_dict
        assert all_dict["test__model1"] is model1
        assert all_dict["other__model2"] is model2

        # Get models from specific namespace
        test_dict = registry.get_registry_dict("test")
        assert len(test_dict) == 1
        assert "test__model1" in test_dict
        assert "other__model2" not in test_dict

    def test_resolve_extends(self):
        """Test resolving parent model references."""
        registry = ModelRegistry()

        base_model = ModelDefinition(
            id="base", name="Base", namespace="test", attributes={}
        )
        mixin_model = ModelDefinition(
            id="mixin", name="Mixin", namespace="test", attributes={}
        )

        registry.register("test", "base", base_model)
        registry.register("test", "mixin", mixin_model)

        # Resolve extends in same namespace
        resolved = registry.resolve_extends("test", ["base", "mixin"])
        assert len(resolved) == 2
        assert resolved[0] is base_model
        assert resolved[1] is mixin_model

    def test_resolve_extends_cross_namespace(self):
        """Test resolving parent models across namespaces."""
        registry = ModelRegistry()

        base_model = ModelDefinition(
            id="base", name="Base", namespace="core", attributes={}
        )
        registry.register("core", "base", base_model)

        # Should find model from different namespace
        resolved = registry.resolve_extends("game", ["base"])
        assert len(resolved) == 1
        assert resolved[0] is base_model

    def test_resolve_extends_missing_parent(self):
        """Test error when parent model not found."""
        registry = ModelRegistry()

        with pytest.raises(KeyError, match="Parent model 'missing' not found"):
            registry.resolve_extends("test", ["missing"])

    def test_registry_overwrite_warning(self, caplog):
        """Test warning when overwriting existing model."""
        registry = ModelRegistry()

        model1 = ModelDefinition(
            id="test", name="Test 1", namespace="test", attributes={}
        )
        model2 = ModelDefinition(
            id="test", name="Test 2", namespace="test", attributes={}
        )

        registry.register("test", "test", model1)
        registry.register("test", "test", model2)  # Should warn about overwrite

        assert "already registered" in caplog.text
        assert registry.get("test", "test") is model2

    def test_registry_contains(self):
        """Test __contains__ method."""
        registry = ModelRegistry()

        model_def = ModelDefinition(
            id="test", name="Test", namespace="test", attributes={}
        )
        registry.register("test", "test", model_def)

        assert "test__test" in registry
        assert "test__missing" not in registry

    def test_registry_len(self):
        """Test __len__ method."""
        registry = ModelRegistry()

        assert len(registry) == 0

        model1 = ModelDefinition(
            id="model1", name="Model 1", namespace="test", attributes={}
        )
        model2 = ModelDefinition(
            id="model2", name="Model 2", namespace="test", attributes={}
        )

        registry.register("test", "model1", model1)
        assert len(registry) == 1

        registry.register("test", "model2", model2)
        assert len(registry) == 2

    def test_registry_repr(self):
        """Test __repr__ method."""
        registry = ModelRegistry()

        model_def = ModelDefinition(
            id="test", name="Test", namespace="test", attributes={}
        )
        registry.register("test", "test", model_def)

        repr_str = repr(registry)
        assert "ModelRegistry" in repr_str
        assert "1 models" in repr_str
        assert "1 namespaces" in repr_str


class TestModelDefinitionAutoRegistration:
    """Test automatic registration of ModelDefinitions."""

    def setup_method(self):
        """Clear registry before each test."""
        clear_registry()

    def teardown_method(self):
        """Clear registry after each test."""
        clear_registry()

    def test_model_auto_registration(self):
        """Test that models are automatically registered when created."""
        model_def = ModelDefinition(
            id="auto_test",
            name="Auto Test",
            namespace="test",
            attributes={"name": AttributeDefinition(type="str", required=True)},
        )

        # Should be automatically registered
        retrieved = get_model("test", "auto_test")
        assert retrieved is model_def

    def test_model_default_namespace(self):
        """Test model with default namespace."""
        model_def = ModelDefinition(
            id="default_test", name="Default Test", attributes={}
        )

        # Should be registered in default namespace
        retrieved = get_model("default", "default_test")
        assert retrieved is model_def

    def test_model_custom_namespace(self):
        """Test model with custom namespace."""
        model_def = ModelDefinition(
            id="custom_test",
            name="Custom Test",
            namespace="custom.namespace.test",
            attributes={},
        )

        # Should be registered in custom namespace
        retrieved = get_model("custom.namespace.test", "custom_test")
        assert retrieved is model_def

    def test_namespace_validation(self):
        """Test namespace validation."""
        # Valid namespaces
        ModelDefinition(id="test1", name="Test 1", namespace="valid", attributes={})
        ModelDefinition(
            id="test2", name="Test 2", namespace="valid-namespace", attributes={}
        )
        ModelDefinition(
            id="test3", name="Test 3", namespace="valid_namespace", attributes={}
        )
        ModelDefinition(
            id="test4", name="Test 4", namespace="valid.namespace", attributes={}
        )

        # Invalid namespace should raise error
        with pytest.raises(ValueError, match="Namespace cannot be empty"):
            ModelDefinition(id="test5", name="Test 5", namespace="", attributes={})

        with pytest.raises(ValueError, match="Namespace must contain only"):
            ModelDefinition(
                id="test6", name="Test 6", namespace="invalid@namespace", attributes={}
            )


class TestGlobalRegistryFunctions:
    """Test global registry convenience functions."""

    def setup_method(self):
        """Clear registry before each test."""
        clear_registry()

    def teardown_method(self):
        """Clear registry after each test."""
        clear_registry()

    def test_register_model_function(self):
        """Test register_model convenience function."""
        model_def = ModelDefinition(
            id="function_test",
            name="Function Test",
            namespace="manual",  # This will auto-register in "manual" namespace
            attributes={},
        )

        # Should be auto-registered already, but let's register manually in
        # different namespace
        register_model("test", model_def)

        # Should now be available in both namespaces
        retrieved_manual = get_model("manual", "function_test")
        retrieved_test = get_model("test", "function_test")

        assert retrieved_manual is model_def
        assert retrieved_test is model_def

    def test_get_model_function(self):
        """Test get_model convenience function."""
        model_def = ModelDefinition(
            id="get_test", name="Get Test", namespace="test", attributes={}
        )

        # Should be auto-registered
        retrieved = get_model("test", "get_test")
        assert retrieved is model_def

        # Non-existent model should return None
        missing = get_model("test", "missing")
        assert missing is None

    def test_clear_registry_function(self):
        """Test clear_registry convenience function."""
        model_def = ModelDefinition(
            id="clear_test", name="Clear Test", namespace="test", attributes={}
        )

        # Should be auto-registered
        assert get_model("test", "clear_test") is model_def

        # Clear registry
        count = clear_registry()
        assert count >= 1  # At least our model

        # Should no longer be available
        assert get_model("test", "clear_test") is None
