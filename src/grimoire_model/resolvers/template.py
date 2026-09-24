"""
Template resolution for grimoire-model package.

Provides template resolution capabilities using Jinja2 with support for model
contexts, variable extraction, and caching.
"""

import ast
import json
import re
from typing import Any, Dict, Protocol, Set, cast

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

        # Jinja2 ships globals (range, dict, namespace, cycler, joiner,
        # lipsum) that are reachable from any expression. In a model
        # expression that is a hazard rather than a feature: a misspelled
        # or missing attribute whose name collides with one of them
        # resolves to the builtin instead of raising, so `{{ range }}`
        # silently renders "<class 'range'>" onto a model. Both `range`
        # and `dict` are plausible attribute names. Clearing globals makes
        # every unresolved name raise under StrictUndefined, and lets an
        # attribute legitimately be called `range`. Filters live in
        # `env.filters` and are unaffected.
        self.env.globals.clear()

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
            found, value = self._check_simple_variable(template_str, enhanced_context)
            if found:
                return value

            # Check if this is a pure expression template (just {{ expression }})
            # If so, use compile_expression to preserve object types
            is_pure_expr, expr_str = self._check_pure_expression(template_str)
            if is_pure_expr:
                # Validate that all required variables exist before compiling
                # This ensures we get proper error messages for undefined variables
                try:
                    # Parse to check for undefined variables
                    ast_tree = self.env.parse(template_str)
                    undefined_vars = meta.find_undeclared_variables(ast_tree)
                    missing_vars = [
                        v for v in undefined_vars if v not in enhanced_context
                    ]
                    if missing_vars:
                        # Let the normal render path handle this to get proper error
                        raise ValueError(f"Undefined variables: {missing_vars}")

                    # All variables exist, safe to use compile_expression
                    expr = self.env.compile_expression(expr_str)
                    result = expr(**enhanced_context)
                    return result
                except ValueError:
                    # Fall back to render for proper error handling
                    pass

            # Render template as string
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
        """Return the evaluation context: the caller's data, unaltered.

        Earlier versions injected Python builtins (``max``, ``min``, ``sum``,
        ``len``, ``abs``, ``round``) here. That was not Jinja2, so expressions
        using them were not portable, and because the builtins were written
        over the caller's data, a model attribute named ``round`` or ``max``
        was silently replaced by a function. Aggregation uses Jinja2 filters
        (``xs | sum``, ``xs | max``, ``xs | length``) instead.
        """
        return context.copy()

    def _check_pure_expression(self, template_str: str) -> tuple[bool, str]:
        """Check if template is a pure expression (just {{ ... }}) with no text.

        Returns:
            A tuple of (is_pure, expression) where:
            - is_pure: True if this is a pure expression template
            - expression: The expression string without {{ }}
        """
        # Match pattern: {{ expression }} with optional whitespace
        match = re.match(r"^\s*\{\{\s*(.+)\s*\}\}\s*$", template_str, re.DOTALL)
        if not match:
            return (False, "")

        # Check if there are multiple Jinja2 expressions by looking for
        # }} followed by content followed by {{
        # This pattern would indicate "{{ expr1 }} text {{ expr2 }}"
        if re.search(r"\}\}.*\{\{", template_str):
            return (False, "")

        return (True, match.group(1))

    def _check_simple_variable(
        self, template_str: str, context: Dict[str, Any]
    ) -> tuple[bool, Any]:
        """Check if template is a simple variable reference and return the value
        directly.

        Handles both simple variables ({{ variable }}) and dotted paths
        ({{ outputs.knave }}) by navigating through nested dictionaries.

        Returns:
            A tuple of (found, value) where:
            - found: True if this is a simple variable reference with existing path
            - value: The actual value (preserves type, can be None, dict, list, etc.)
        """
        # Match patterns like {{ variable }} or {{ path.to.variable }}
        match = re.match(
            r"^\s*\{\{\s*([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*)\s*\}\}\s*$", template_str
        )
        if match:
            var_path = match.group(1)

            # Handle simple (non-dotted) variable
            if "." not in var_path:
                if var_path in context:
                    return (True, context[var_path])
                return (False, None)

            # Handle dotted path by navigating through the structure
            path_parts = var_path.split(".")
            current = context

            try:
                for part in path_parts:
                    if isinstance(current, dict) and part in current:
                        current = current[part]
                    else:
                        # Path doesn't exist
                        return (False, None)

                # Found the path - return the actual value (preserves type)
                return (True, current)

            except (KeyError, TypeError):
                # Path navigation failed
                return (False, None)

        return (False, None)

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
        resolver_type: Type of resolver to create. Only 'jinja2' exists.
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
    else:
        raise ValueError(
            f"Unknown resolver type: {resolver_type}. Only 'jinja2' is supported; "
            "the `$`-syntax 'model_context' resolver was removed in 0.7.0."
        )

    if caching:
        resolver = cast(TemplateResolver, CachingTemplateResolver(resolver))

    return resolver
