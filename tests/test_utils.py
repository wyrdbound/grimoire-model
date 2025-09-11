"""Tests for utility functions."""

import pytest

from grimoire_model.core.exceptions import InheritanceError
from grimoire_model.core.schema import AttributeDefinition, ModelDefinition
from grimoire_model.utils.inheritance import (
    build_inheritance_graph,
    check_inheritance_conflicts,
    find_inheritance_cycles,
    resolve_model_inheritance,
    validate_model_registry,
)
from grimoire_model.utils.paths import (
    delete_nested_value,
    flatten_dict,
    get_nested_value,
    has_nested_value,
    merge_nested_dicts,
    set_nested_value,
    unflatten_dict,
)


class TestPathUtils:
    """Test path utility functions."""

    def test_get_nested_value_simple(self):
        """Test getting simple nested values."""
        data = {
            "name": "John",
            "age": 30,
            "address": {"street": "123 Main St", "city": "New York", "country": "USA"},
        }

        # Simple values
        assert get_nested_value(data, "name") == "John"
        assert get_nested_value(data, "age") == 30

        # Nested values
        assert get_nested_value(data, "address.street") == "123 Main St"
        assert get_nested_value(data, "address.city") == "New York"
        assert get_nested_value(data, "address.country") == "USA"

    def test_get_nested_value_missing(self):
        """Test getting missing nested values."""
        data = {"name": "John"}

        # Missing top-level key
        assert get_nested_value(data, "age") is None
        assert get_nested_value(data, "age", "default") == "default"

        # Missing nested key
        assert get_nested_value(data, "address.street") is None
        assert get_nested_value(data, "address.street", "default") == "default"

    def test_get_nested_value_invalid_path(self):
        """Test getting values with invalid paths."""
        data = {"name": "John", "age": 30}

        # Try to access nested property on non-dict value
        assert get_nested_value(data, "name.length") is None
        assert get_nested_value(data, "age.invalid") is None

    def test_set_nested_value_simple(self):
        """Test setting simple nested values."""
        data = {}

        # Simple values
        set_nested_value(data, "name", "John")
        set_nested_value(data, "age", 30)

        assert data["name"] == "John"
        assert data["age"] == 30

    def test_set_nested_value_create_path(self):
        """Test setting nested values that create intermediate dicts."""
        data = {}

        set_nested_value(data, "address.street", "123 Main St")
        set_nested_value(data, "address.city", "New York")

        assert data["address"]["street"] == "123 Main St"
        assert data["address"]["city"] == "New York"

    def test_set_nested_value_overwrite(self):
        """Test overwriting existing values."""
        data = {"name": "John", "address": {"city": "Old City"}}

        set_nested_value(data, "name", "Jane")
        set_nested_value(data, "address.city", "New York")

        assert data["name"] == "Jane"
        assert data["address"]["city"] == "New York"

    def test_set_nested_value_invalid_path(self):
        """Test setting nested values with invalid intermediate types."""
        data = {"name": "John"}

        # Try to set nested property on non-dict value
        with pytest.raises(TypeError):
            set_nested_value(data, "name.length", 4)

    def test_delete_nested_value(self):
        """Test deleting nested values."""
        data = {
            "name": "John",
            "address": {"street": "123 Main St", "city": "New York"},
        }

        # Delete simple value
        delete_nested_value(data, "name")
        assert "name" not in data

        # Delete nested value
        delete_nested_value(data, "address.street")
        assert "street" not in data["address"]
        assert "city" in data["address"]  # Other values remain

    def test_delete_nested_value_missing(self):
        """Test deleting missing values."""
        data = {"name": "John"}

        # Deleting missing key should not raise error
        delete_nested_value(data, "age")
        delete_nested_value(data, "address.street")

        assert data == {"name": "John"}

    def test_has_nested_value(self):
        """Test checking for nested value existence."""
        data = {
            "name": "John",
            "address": {
                "street": "123 Main St",
                "city": None,  # Explicitly None value
            },
        }

        # Existing values
        assert has_nested_value(data, "name") is True
        assert has_nested_value(data, "address.street") is True

        # None value should still return True (key exists)
        assert has_nested_value(data, "address.city") is True

        # Missing values
        assert has_nested_value(data, "age") is False
        assert has_nested_value(data, "address.country") is False
        assert has_nested_value(data, "missing.path") is False

    def test_flatten_dict_simple(self):
        """Test flattening simple nested dictionaries."""
        data = {
            "name": "John",
            "age": 30,
            "address": {"street": "123 Main St", "city": "New York"},
        }

        flattened = flatten_dict(data)

        expected = {
            "name": "John",
            "age": 30,
            "address.street": "123 Main St",
            "address.city": "New York",
        }

        assert flattened == expected

    def test_flatten_dict_deep_nesting(self):
        """Test flattening deeply nested dictionaries."""
        data = {
            "user": {
                "profile": {
                    "personal": {"name": "John", "age": 30},
                    "contact": {"email": "john@example.com"},
                }
            }
        }

        flattened = flatten_dict(data)

        expected = {
            "user.profile.personal.name": "John",
            "user.profile.personal.age": 30,
            "user.profile.contact.email": "john@example.com",
        }

        assert flattened == expected

    def test_flatten_dict_custom_separator(self):
        """Test flattening with custom separator."""
        data = {"a": {"b": {"c": "value"}}}

        flattened = flatten_dict(data, separator="/")
        assert flattened == {"a/b/c": "value"}

    def test_flatten_dict_non_dict_values(self):
        """Test flattening with non-dict values."""
        data = {
            "name": "John",
            "tags": ["python", "testing"],
            "config": {"enabled": True, "count": 5},
        }

        flattened = flatten_dict(data)

        expected = {
            "name": "John",
            "tags": ["python", "testing"],  # List preserved
            "config.enabled": True,
            "config.count": 5,
        }

        assert flattened == expected

    def test_unflatten_dict(self):
        """Test unflattening dictionaries."""
        flattened = {
            "name": "John",
            "age": 30,
            "address.street": "123 Main St",
            "address.city": "New York",
            "user.profile.email": "john@example.com",
        }

        unflattened = unflatten_dict(flattened)

        expected = {
            "name": "John",
            "age": 30,
            "address": {"street": "123 Main St", "city": "New York"},
            "user": {"profile": {"email": "john@example.com"}},
        }

        assert unflattened == expected

    def test_unflatten_dict_custom_separator(self):
        """Test unflattening with custom separator."""
        flattened = {"a/b/c": "value"}
        unflattened = unflatten_dict(flattened, separator="/")

        expected = {"a": {"b": {"c": "value"}}}

        assert unflattened == expected

    def test_flatten_unflatten_roundtrip(self):
        """Test that flatten/unflatten is a reversible operation."""
        original = {
            "name": "John",
            "details": {
                "age": 30,
                "address": {
                    "street": "123 Main St",
                    "coordinates": {"lat": 40.7128, "lng": -74.0060},
                },
            },
        }

        flattened = flatten_dict(original)
        unflattened = unflatten_dict(flattened)

        assert unflattened == original

    def test_merge_nested_dicts_simple(self):
        """Test merging simple nested dictionaries."""
        dict1 = {
            "name": "John",
            "age": 30,
            "address": {"street": "123 Main St", "city": "New York"},
        }

        dict2 = {
            "age": 31,  # Override
            "email": "john@example.com",  # New
            "address": {
                "city": "Boston",  # Override nested
                "country": "USA",  # New nested
            },
        }

        result = merge_nested_dicts(dict1, dict2)

        expected = {
            "name": "John",
            "age": 31,
            "email": "john@example.com",
            "address": {"street": "123 Main St", "city": "Boston", "country": "USA"},
        }

        assert result == expected

    def test_merge_nested_dicts_deep(self):
        """Test merging deeply nested dictionaries."""
        dict1 = {
            "level1": {"level2": {"level3": {"value1": "old", "value2": "preserved"}}}
        }

        dict2 = {"level1": {"level2": {"level3": {"value1": "new", "value3": "added"}}}}

        result = merge_nested_dicts(dict1, dict2)

        expected = {
            "level1": {
                "level2": {
                    "level3": {
                        "value1": "new",
                        "value2": "preserved",
                        "value3": "added",
                    }
                }
            }
        }

        assert result == expected

    def test_merge_nested_dicts_overwrite_behavior(self):
        """Test merge behavior when overwriting non-dict with dict."""
        dict1 = {"config": "simple_value", "nested": {"keep": "this"}}

        dict2 = {"config": {"complex": "value"}, "nested": {"add": "this"}}

        result = merge_nested_dicts(dict1, dict2)

        expected = {
            "config": {"complex": "value"},
            "nested": {"keep": "this", "add": "this"},
        }

        assert result == expected


class TestInheritanceUtils:
    """Test inheritance utility functions."""

    def test_resolve_model_inheritance_single(self):
        """Test resolving single inheritance."""
        from typing import Any, Dict, Union, cast

        # Create parent model (use proper type annotations)
        parent_attrs: Dict[str, Union[AttributeDefinition, Dict[str, Any]]] = cast(
            Dict[str, Union[AttributeDefinition, Dict[str, Any]]],
            {
                "name": {"type": "str", "required": True},
                "created_at": {"type": "str", "computed": True, "derived": "{{now()}}"},
            },
        )
        parent = ModelDefinition(
            id="base_model", name="BaseModel", attributes=parent_attrs
        )

        # Create child model
        child_attrs: Dict[str, Union[AttributeDefinition, Dict[str, Any]]] = cast(
            Dict[str, Union[AttributeDefinition, Dict[str, Any]]],
            {
                "email": {"type": "str", "required": True},
                "name": {"type": "str", "required": False},  # Override parent
            },
        )
        child = ModelDefinition(
            id="user_model",
            name="UserModel",
            extends=["base_model"],
            attributes=child_attrs,
        )

        models = {"base_model": parent, "user_model": child}

        resolved = resolve_model_inheritance(child, models)

        # Should have all attributes with child overrides
        assert "name" in resolved.attributes
        assert "email" in resolved.attributes
        assert "created_at" in resolved.attributes

        # Child should override parent - check the resolved attribute object
        name_attr = resolved.attributes["name"]
        assert isinstance(name_attr, AttributeDefinition)
        assert name_attr.required is False

    def test_resolve_model_inheritance_no_inheritance(self):
        """Test resolving model without inheritance."""
        from typing import Any, Dict, Union, cast

        attrs: Dict[str, Union[AttributeDefinition, Dict[str, Any]]] = cast(
            Dict[str, Union[AttributeDefinition, Dict[str, Any]]],
            {"name": {"type": "str", "required": True}},
        )
        model = ModelDefinition(id="simple_model", name="SimpleModel", attributes=attrs)

        models = {"simple_model": model}

        resolved = resolve_model_inheritance(model, models)

        # Should be the same model
        assert resolved.id == model.id
        assert len(resolved.attributes) == len(model.attributes)

    def test_check_inheritance_conflicts(self):
        """Test checking for inheritance conflicts."""
        from typing import Any, Dict, Union, cast

        # Create parent with str type
        parent_attrs: Dict[str, Union[AttributeDefinition, Dict[str, Any]]] = cast(
            Dict[str, Union[AttributeDefinition, Dict[str, Any]]],
            {"field": {"type": "str", "required": True}},
        )
        parent = ModelDefinition(id="parent", name="Parent", attributes=parent_attrs)

        # Create child with conflicting int type
        child_attrs: Dict[str, Union[AttributeDefinition, Dict[str, Any]]] = cast(
            Dict[str, Union[AttributeDefinition, Dict[str, Any]]],
            {
                "field": {"type": "int", "required": True}  # Conflicting type
            },
        )
        child = ModelDefinition(
            id="child", name="Child", extends=["parent"], attributes=child_attrs
        )

        models = {"parent": parent, "child": child}

        conflicts = check_inheritance_conflicts(child, models)
        assert len(conflicts) > 0
        assert any("conflicting types" in conflict.lower() for conflict in conflicts)

    def test_check_inheritance_no_conflicts(self):
        """Test checking inheritance with no conflicts."""
        from typing import Any, Dict, Union, cast

        # Create compatible models
        parent_attrs: Dict[str, Union[AttributeDefinition, Dict[str, Any]]] = cast(
            Dict[str, Union[AttributeDefinition, Dict[str, Any]]],
            {"field": {"type": "str", "required": True}},
        )
        parent = ModelDefinition(id="parent", name="Parent", attributes=parent_attrs)

        child_attrs: Dict[str, Union[AttributeDefinition, Dict[str, Any]]] = cast(
            Dict[str, Union[AttributeDefinition, Dict[str, Any]]],
            {
                "field": {"type": "str", "required": False},  # Compatible override
                "new_field": {"type": "int", "required": True},
            },
        )
        child = ModelDefinition(
            id="child", name="Child", extends=["parent"], attributes=child_attrs
        )

        models = {"parent": parent, "child": child}

        conflicts = check_inheritance_conflicts(child, models)
        assert len(conflicts) == 0

    def test_find_inheritance_cycles(self):
        """Test finding inheritance cycles."""
        # Create models with circular inheritance
        model_a = ModelDefinition(id="A", name="A", extends=["B"])
        model_b = ModelDefinition(id="B", name="B", extends=["C"])
        model_c = ModelDefinition(
            id="C",
            name="C",
            extends=["A"],  # Creates cycle
        )

        models = {"A": model_a, "B": model_b, "C": model_c}

        cycles = find_inheritance_cycles(models)
        assert len(cycles) > 0

        # Should find the cycle
        cycle = cycles[0]
        assert "A" in cycle
        assert "B" in cycle
        assert "C" in cycle

    def test_find_inheritance_no_cycles(self):
        """Test finding inheritance with no cycles."""
        # Create models with valid inheritance
        model_a = ModelDefinition(id="A", name="A", extends=["B"])
        model_b = ModelDefinition(id="B", name="B", extends=["C"])
        model_c = ModelDefinition(
            id="C",
            name="C",  # No inheritance
        )

        models = {"A": model_a, "B": model_b, "C": model_c}

        cycles = find_inheritance_cycles(models)
        assert len(cycles) == 0

    def test_resolve_inheritance_missing_parent(self):
        """Test resolving inheritance with missing parent."""
        from typing import Any, Dict, Union, cast

        child_attrs: Dict[str, Union[AttributeDefinition, Dict[str, Any]]] = cast(
            Dict[str, Union[AttributeDefinition, Dict[str, Any]]],
            {"name": {"type": "str", "required": True}},
        )
        child = ModelDefinition(
            id="child", name="Child", extends=["missing_parent"], attributes=child_attrs
        )

        models = {"child": child}  # Missing parent

        with pytest.raises(InheritanceError) as exc_info:
            resolve_model_inheritance(child, models)

        assert "not found" in str(exc_info.value)

    def test_build_inheritance_graph(self):
        """Test building inheritance graph."""
        parent = ModelDefinition(id="parent", name="Parent")

        child1 = ModelDefinition(id="child1", name="Child1", extends=["parent"])

        child2 = ModelDefinition(id="child2", name="Child2", extends=["parent"])

        models = {"parent": parent, "child1": child1, "child2": child2}

        graph = build_inheritance_graph(models)

        # Parent should have two children
        assert len(graph["parent"]) == 2
        assert "child1" in graph["parent"]
        assert "child2" in graph["parent"]

        # Children should have no children
        assert len(graph["child1"]) == 0
        assert len(graph["child2"]) == 0

    def test_validate_model_registry(self):
        """Test model registry validation."""
        # Create valid registry
        parent = ModelDefinition(id="parent", name="Parent")

        child = ModelDefinition(id="child", name="Child", extends=["parent"])

        valid_models = {"parent": parent, "child": child}

        errors = validate_model_registry(valid_models)
        assert len(errors) == 0

        # Create invalid registry with missing parent
        invalid_child = ModelDefinition(
            id="invalid_child", name="InvalidChild", extends=["missing_parent"]
        )

        invalid_models = {"invalid_child": invalid_child}

        errors = validate_model_registry(invalid_models)
        assert len(errors) > 0
        assert any("unknown model" in error.lower() for error in errors)
