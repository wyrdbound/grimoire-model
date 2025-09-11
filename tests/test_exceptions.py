"""Tests for exception functionality."""

from grimoire_model.core.exceptions import (
    DependencyError,
    GrimoireModelError,
    InheritanceError,
    ModelValidationError,
    TemplateResolutionError,
)


class TestGrimoireModelError:
    """Test base exception class."""

    def test_basic_exception(self):
        """Test basic exception creation."""
        error = GrimoireModelError("Test error")
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.context == {}

    def test_exception_with_context(self):
        """Test exception with context."""
        context = {"model_id": "test", "field": "name"}
        error = GrimoireModelError("Test error", context=context)
        assert error.context == context
        expected_str = "Test error (context: model_id=test, field=name)"
        assert str(error) == expected_str

    def test_exception_inheritance(self):
        """Test exception inheritance."""
        error = GrimoireModelError("Test")
        assert isinstance(error, Exception)


class TestModelValidationError:
    """Test model validation error."""

    def test_validation_error_basic(self):
        """Test basic validation error."""
        error = ModelValidationError("Validation failed")
        assert "Validation failed" in str(error)

    def test_validation_error_with_field(self):
        """Test validation error with field information."""
        error = ModelValidationError(
            "Field validation failed",
            field_name="age",
            field_value=15,
            validation_errors=["Must be 18 or older"],
        )
        assert error.field_name == "age"
        assert error.field_value == 15
        assert error.validation_errors == ["Must be 18 or older"]

    def test_validation_error_str_representation(self):
        """Test validation error string representation."""
        error = ModelValidationError(
            "Validation failed",
            field_name="test_field",
            validation_errors=["error1", "error2"],
        )
        error_str = str(error)
        assert "Validation failed" in error_str
        assert "field: test_field" in error_str


class TestTemplateResolutionError:
    """Test template resolution error."""

    def test_template_error_basic(self):
        """Test basic template resolution error."""
        error = TemplateResolutionError("Template failed")
        assert "Template failed" in str(error)

    def test_template_error_with_details(self):
        """Test template error with details."""
        error = TemplateResolutionError(
            "Template resolution failed",
            template_str="{{ invalid }}",
            template_variables=["invalid"],
            context={"available": ["valid"]},
        )
        assert error.template_str == "{{ invalid }}"
        assert error.template_variables == ["invalid"]
        assert error.context == {"available": ["valid"]}

    def test_template_error_str_representation(self):
        """Test template error string representation."""
        error = TemplateResolutionError(
            "Template failed", template_str="{{ test }}", template_variables=["test"]
        )
        error_str = str(error)
        assert "Template failed" in error_str
        assert "template: {{ test }}" in error_str


class TestInheritanceError:
    """Test inheritance error."""

    def test_inheritance_error_basic(self):
        """Test basic inheritance error."""
        error = InheritanceError("Inheritance failed")
        assert "Inheritance failed" in str(error)

    def test_inheritance_error_with_details(self):
        """Test inheritance error with details."""
        error = InheritanceError(
            "Circular dependency",
            model_id="test_model",
            inheritance_chain=["test_model", "parent1", "parent2", "test_model"],
        )
        assert error.model_id == "test_model"
        assert error.inheritance_chain == [
            "test_model",
            "parent1",
            "parent2",
            "test_model",
        ]


class TestDependencyError:
    """Test dependency error."""

    def test_dependency_error_basic(self):
        """Test basic dependency error."""
        error = DependencyError("Dependency failed")
        assert "Dependency failed" in str(error)

    def test_dependency_error_with_details(self):
        """Test dependency error with details."""
        error = DependencyError(
            "Circular dependency in derived fields",
            field_name="computed_field",
            dependencies=["field1", "field2"],
            dependency_chain=["computed_field", "field1", "computed_field"],
        )
        assert error.field_name == "computed_field"
        assert error.dependencies == ["field1", "field2"]
        assert error.dependency_chain == ["computed_field", "field1", "computed_field"]


class TestExceptionStringRepresentations:
    """Test exception string representations."""

    def test_error_str_formatting(self):
        """Test that error messages format correctly."""
        # Test with context
        error = ModelValidationError(
            "Test error", field_name="test", validation_errors=["error1", "error2"]
        )
        error_str = str(error)
        assert "Test error" in error_str
        assert "field: test" in error_str
        assert "errors: [error1, error2]" in error_str

    def test_template_error_formatting(self):
        """Test template error formatting."""
        error = TemplateResolutionError(
            "Template failed",
            template_str="{{ bad }}",
            template_variables=["bad"],
            context={"good": "value"},
        )
        error_str = str(error)
        assert "Template failed" in error_str
        assert "template: {{ bad }}" in error_str
        assert "variables: [bad]" in error_str
        assert "context: good=value" in error_str
