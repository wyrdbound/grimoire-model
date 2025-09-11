"""
Template resolution for grimoire-model package.

Provides template resolution capabilities using Jinja2 with support for model
contexts, variable extraction, and caching.
"""

import ast
import json
import re
from typing import Any, Dict, Optional, Protocol, Set, cast

import jinja2
from jinja2 import BaseLoader, Environment, TemplateError, meta

from ..core.exceptions import TemplateResolutionError
from ..logging import get_logger

logger = get_logger("resolvers.template")


class TemplateResolver(Protocol):
    """Protocol for template resolution."""

    def resolve_template(self, template_str: str, context: Dict[str, Any]) -> Any:
        """Resolve a template string with the given context."""
        ...

    def is_template(self, value: str) -> bool:
        """Check if a string contains template syntax."""
        ...

    def extract_variables(self, template_str: str) -> Set[str]:
        """Extract variable names from a template string."""
        ...


class StringTemplateLoader(BaseLoader):
    """Custom Jinja2 loader for string templates."""

    def __init__(self):
        self.templates: Dict[str, str] = {}

    def get_source(self, environment: Environment, template: str) -> tuple:
        """Get template source."""
        if template in self.templates:
            source = self.templates[template]
            return source, None, lambda: True
        raise TemplateError(f"Template '{template}' not found")

    def add_template(self, name: str, source: str) -> None:
        """Add a template to the loader."""
        self.templates[name] = source


class Jinja2TemplateResolver:
    """Jinja2-based template resolver implementation."""

    def __init__(self, **jinja_kwargs):
        """Initialize with optional Jinja2 environment customizations."""
        loader = StringTemplateLoader()

        # Default Jinja2 environment settings
        env_kwargs = {
            "loader": loader,
            "undefined": jinja2.StrictUndefined,  # Fail on undefined variables
            "trim_blocks": True,
            "lstrip_blocks": True,
        }
        env_kwargs.update(jinja_kwargs)

        self.env = Environment(**cast(Any, env_kwargs))
        self.loader = loader

        # Template detection patterns
        self._template_patterns = [
            re.compile(r"\{\{.*?\}\}"),  # Variables: {{ var }}
            re.compile(r"\{%.*?%\}"),  # Statements: {% if %}
            re.compile(r"\{#.*?#\}"),  # Comments: {# comment #}
        ]

    def resolve_template(self, template_str: str, context: Dict[str, Any]) -> Any:
        """Resolve a template string with the given context."""
        if not isinstance(template_str, str):
            return template_str

        # Skip if no template syntax
        if not self.is_template(template_str):
            return template_str

        try:
            # Create enhanced context for better object access
            enhanced_context = self._enhance_context(context)

            # Check for simple variable reference
            simple_var = self._check_simple_variable(template_str, enhanced_context)
            if simple_var is not None:
                return simple_var

            # Render template
            template = self.env.from_string(template_str)
            result = template.render(enhanced_context)

            # Try to parse as structured data if it looks like it
            parsed_result = self._try_parse_structured_data(result)
            if parsed_result is not None:
                return parsed_result

            return result

        except Exception as e:
            error_msg = (
                f"Template resolution failed for '{template_str}': {e}. "
                f"Available context keys: "
                f"{list(context.keys()) if isinstance(context, dict) else 'N/A'}"
            )
            logger.error(error_msg)
            raise TemplateResolutionError(
                error_msg,
                template_str=template_str,
                template_variables=list(self.extract_variables(template_str)),
                context={
                    "available_keys": list(context.keys())
                    if isinstance(context, dict)
                    else []
                },
            ) from e

    def is_template(self, value: str) -> bool:
        """Check if a string contains template syntax."""
        if not isinstance(value, str):
            return False

        return any(pattern.search(value) for pattern in self._template_patterns)

    def extract_variables(self, template_str: str) -> Set[str]:
        """Extract variable names from a template string."""
        if not isinstance(template_str, str):
            return set()

        try:
            ast_tree = self.env.parse(template_str)
            return set(meta.find_undeclared_variables(ast_tree))
        except Exception as e:
            logger.warning(f"Could not extract variables from template: {e}")
            return set()

    def _enhance_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance context with additional utility variables."""
        enhanced = context.copy()

        # Add underscore-prefixed dollar access since $ can't start Jinja2 variables
        if "$" in enhanced:
            enhanced["_dollar"] = enhanced["$"]

        # Add Python built-ins that are commonly needed
        import builtins

        enhanced.update({
            "max": builtins.max,
            "min": builtins.min,
            "sum": builtins.sum,
            "len": builtins.len,
            "abs": builtins.abs,
            "round": builtins.round,
        })

        return enhanced

    def _check_simple_variable(self, template_str: str, context: Dict[str, Any]) -> Any:
        """Check if template is a simple variable reference and return the value
        directly."""
        # Match patterns like {{ variable }} or {{variable}}
        match = re.match(
            r"^\s*\{\{\s*([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*)\s*\}\}\s*$", template_str
        )
        if match:
            var_name = match.group(1)
            if var_name in context:
                return context[var_name]
        return None

    def _try_parse_structured_data(self, value: str) -> Any:
        """Try to parse a string as structured data."""
        if not isinstance(value, str):
            return None

        # Only try parsing if it looks like structured data
        stripped = value.strip()
        if not (stripped.startswith(("[", "{")) and stripped.endswith(("]", "}"))):
            return None

        # Try JSON first
        try:
            parsed = json.loads(value)
            if isinstance(parsed, (list, dict)):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass

        # Try Python literal evaluation
        try:
            parsed = ast.literal_eval(value)
            if isinstance(parsed, (list, dict)):
                return parsed
        except (ValueError, SyntaxError):
            pass

        return None


class ModelContextTemplateResolver(Jinja2TemplateResolver):
    """Template resolver specifically designed for model contexts.

    Provides additional features for model field references and path resolution.
    Supports both Jinja2 syntax ({{ var }}) and model context syntax ($var).
    """

    def __init__(self, **jinja_kwargs):
        super().__init__(**jinja_kwargs)

        # Add model-specific functions to the environment
        self.env.globals.update({
            "get_field": self._template_get_field,
            "has_field": self._template_has_field,
        })

        # Add pattern for $variable syntax
        self._model_context_pattern = re.compile(r"\$\w+")

    def is_template(self, value: str) -> bool:
        """Check if a string contains template syntax (Jinja2 or model context)."""
        if not isinstance(value, str):
            return False

        # Check for Jinja2 syntax first
        if super().is_template(value):
            return True

        # Check for $variable syntax
        return bool(self._model_context_pattern.search(value))

    def resolve_template(self, template_str: str, context: Dict[str, Any]) -> Any:
        """Resolve template string with support for both Jinja2 and $variable syntax."""
        if not isinstance(template_str, str):
            return template_str

        # Skip if no template syntax
        if not self.is_template(template_str):
            return template_str

        try:
            # Check if this is a $variable template (not Jinja2)
            has_model_context = self._model_context_pattern.search(template_str)
            has_template_patterns = any(
                pattern.search(template_str) for pattern in self._template_patterns
            )
            if has_model_context and not has_template_patterns:
                # Handle $variable substitution
                return self._resolve_model_context_template(template_str, context)
            else:
                # Use parent Jinja2 resolution for {{ }} syntax
                return super().resolve_template(template_str, context)

        except Exception as e:
            error_msg = (
                f"Template resolution failed for '{template_str}': {e}. "
                f"Available context keys: {list(context.keys())}"
            )
            logger.error(error_msg)
            raise TemplateResolutionError(
                error_msg,
                template_str=template_str,
                template_variables=list(
                    self._model_context_pattern.findall(template_str)
                ),
                context={"available_keys": list(context.keys())},
            ) from e

    def _resolve_model_context_template(
        self, template_str: str, context: Dict[str, Any]
    ) -> str:
        """Resolve $variable syntax in template strings."""
        result = template_str

        # Find all $variable references
        variables = self._model_context_pattern.findall(template_str)

        for var_match in variables:
            var_name = var_match[1:]  # Remove the $ prefix

            # Look up the variable in context
            if var_name in context:
                value = context[var_name]
                # Replace $varname with the actual value
                result = result.replace(var_match, str(value))
            else:
                raise KeyError(f"'{var_name}' is undefined")

        return result

    def resolve_with_model_context(
        self,
        template_str: str,
        model_data: Dict[str, Any],
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Resolve template with model data as primary context."""
        context = {"$": model_data}  # Model data available as $

        # Add model fields at top level for easier access
        context.update(model_data)

        if additional_context:
            context.update(additional_context)

        return self.resolve_template(template_str, context)

    def _template_get_field(self, path: str, default: Any = None) -> Any:
        """Template function to get a field value by path."""
        # This would be implemented to work with the current template context
        # For now, return a placeholder that would be replaced with actual
        # implementation
        return f"get_field('{path}', {default})"

    def _template_has_field(self, path: str) -> bool:
        """Template function to check if a field exists."""
        # This would be implemented to work with the current template context
        # For now, return a placeholder that would be replaced with actual
        # implementation
        return False


class CachingTemplateResolver:
    """Wrapper that adds caching to any TemplateResolver."""

    def __init__(self, resolver: TemplateResolver, max_cache_size: int = 1000):
        self.resolver = resolver
        self.max_cache_size = max_cache_size
        self._template_cache: Dict[str, bool] = {}
        self._variable_cache: Dict[str, Set[str]] = {}

    def resolve_template(self, template_str: str, context: Dict[str, Any]) -> Any:
        """Resolve template with caching."""
        # For now, simple implementation without context-based caching
        # In production, you might want to cache based on template + context hash
        return self.resolver.resolve_template(template_str, context)

    def is_template(self, value: str) -> bool:
        """Check if string is template with caching."""
        if value not in self._template_cache:
            if len(self._template_cache) >= self.max_cache_size:
                # Simple LRU: remove oldest entry
                self._template_cache.pop(next(iter(self._template_cache)))

            self._template_cache[value] = self.resolver.is_template(value)

        return self._template_cache[value]

    def extract_variables(self, template_str: str) -> Set[str]:
        """Extract variables with caching."""
        if template_str not in self._variable_cache:
            if len(self._variable_cache) >= self.max_cache_size:
                # Simple LRU: remove oldest entry
                self._variable_cache.pop(next(iter(self._variable_cache)))

            self._variable_cache[template_str] = self.resolver.extract_variables(
                template_str
            )

        return self._variable_cache[template_str]


# Factory function for easy creation
def create_template_resolver(
    resolver_type: str = "jinja2", caching: bool = True, **kwargs
) -> TemplateResolver:
    """Factory function to create template resolvers.

    Args:
        resolver_type: Type of resolver to create ('jinja2', 'model_context')
        caching: Whether to enable caching
        **kwargs: Additional arguments passed to the resolver

    Returns:
        Configured template resolver instance

    Raises:
        ValueError: If resolver_type is not supported
    """
    resolver: TemplateResolver
    if resolver_type == "jinja2":
        resolver = Jinja2TemplateResolver(**kwargs)
    elif resolver_type == "model_context":
        resolver = ModelContextTemplateResolver(**kwargs)
    else:
        raise ValueError(f"Unknown resolver type: {resolver_type}")

    if caching:
        resolver = cast(TemplateResolver, CachingTemplateResolver(resolver))

    return resolver
