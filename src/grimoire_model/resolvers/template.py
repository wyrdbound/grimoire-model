"""
Template resolution for grimoire-model package.

Provides template resolution capabilities using Jinja2 with support for model
contexts, variable extraction, and caching.
"""

import re
import threading
from collections import OrderedDict
from collections.abc import Mapping
from typing import Any, Dict, Optional, Protocol, Set, cast

import jinja2
from jinja2 import BaseLoader, Environment, TemplateError, meta
from jinja2.sandbox import SandboxedEnvironment

from ..core.exceptions import TemplateResolutionError
from ..logging import get_logger

logger = get_logger("resolvers.template")


def _maximal_reference_path(node: Any) -> Optional[str]:
    """The maximal dotted path ending at ``node``, or None if there is none.

    Descends through ``Getattr`` (``a.b``) and ``Getitem`` with a constant
    string key (``a['b']``) to the ``Name`` at the root, joining them with
    ".". Returns None when the base is not a free ``Name``.
    """
    parts = []
    current = node
    while current is not None:
        if isinstance(current, jinja2.nodes.Getattr):
            parts.append(current.attr)
            current = current.node
        elif isinstance(current, jinja2.nodes.Getitem):
            key = current.arg
            if isinstance(key, jinja2.nodes.Const) and isinstance(key.value, str):
                parts.append(key.value)
                current = current.node
            else:
                return None
        elif isinstance(current, jinja2.nodes.Name):
            parts.append(current.name)
            return ".".join(reversed(parts))
        else:
            return None
    return None


def _collect_reference_paths(node: Any, paths: Set[str]) -> None:
    """Collect maximal reference paths from one AST subtree into ``paths``."""
    if isinstance(node, (jinja2.nodes.Getattr, jinja2.nodes.Getitem)):
        path = _maximal_reference_path(node)
        if path is not None:
            paths.add(path)
            return
    if isinstance(node, jinja2.nodes.Name):
        paths.add(node.name)
        return
    for child in node.iter_child_nodes():
        _collect_reference_paths(child, paths)


def extract_reference_paths(expression: str) -> Set[str]:
    """Return every maximal dotted reference path in a Jinja2 expression.

    Parses with a plain ``jinja2.Environment`` (Principle II: the syntax is
    Jinja2 whatever resolver is injected) and returns each free variable's
    maximal dotted path, formed by the ``Getattr`` nodes -- and ``Getitem``
    nodes with a constant string key -- directly above it:

    - ``{{ p.mod + 1 }}`` -> ``{"p.mod"}``
    - ``{{ xs | map(attribute='w') | sum }}`` -> ``{"xs"}``
    - ``{{ a['b'].c }}`` -> ``{"a.b.c"}``
    - ``{{ a[i] }}`` -> ``{"a", "i"}``

    A ``Getitem`` with a non-constant key stops the path at the base.
    """
    env = Environment()
    try:
        ast_tree = env.parse(expression)
    except jinja2.TemplateSyntaxError:
        return set()

    paths: Set[str] = set()
    _collect_reference_paths(ast_tree, paths)
    return paths


class _ModelSandboxedEnvironment(SandboxedEnvironment):
    """Sandboxed environment where a mapping exposes its data, not its methods.

    In an expression, ``x.name`` on a mapping means the data at ``name``. For
    a plain ``dict`` or a ``GrimoireModel``, Jinja2's ``getattr`` would find
    ``items`` / ``keys`` / ``values`` / ``get`` before the key, so the two
    evaluation paths disagreed and an attribute with one of those names was
    unreachable. This override looks the key up first.

    A name that is not a key is undefined, **not** a dict method: a mapping's
    methods are not the model's data, and returning one would be a silent
    failure (``{{ g.values }}`` rendering a bound method). Non-mappings keep
    the sandbox's ``getattr``, and with it its safety checks.
    """

    def getattr(self, obj: Any, attribute: str) -> Any:
        if isinstance(obj, Mapping):
            if attribute in obj:
                return obj[attribute]
            return self.undefined(obj=obj, name=attribute)
        return super().getattr(obj, attribute)


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

        # Model definitions are content: once GRIMOIRE systems are distributed
        # they are third-party input. A plain `Environment` lets an expression
        # walk to arbitrary Python classes
        # (`{{ ''.__class__.__mro__[1].__subclasses__() }}`); the sandbox
        # blocks attribute access to unsafe names. Clearing globals below is
        # still required -- sandboxing does not remove them.
        self.env = _ModelSandboxedEnvironment(**cast(Any, env_kwargs))

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
            # If so, compile it to preserve the value's type. An expression
            # that cannot be resolved must raise: `undefined_to_none=False`
            # keeps a `StrictUndefined` result as an `Undefined` (rather than
            # turning it into `None`), and an `Undefined` result is an error.
            is_pure_expr, expr_str = self._check_pure_expression(template_str)
            if is_pure_expr:
                expr = self.env.compile_expression(expr_str, undefined_to_none=False)
                result = expr(**enhanced_context)
                if isinstance(result, jinja2.Undefined):
                    raise jinja2.UndefinedError(
                        f"'{template_str}' references an undefined name"
                    )
                return result

            # Render template as string. Only a template that is exactly one
            # `{{ expression }}` keeps its value's type (handled above); text
            # around an expression renders to text and stays text. Never
            # recover a type by parsing the rendered result -- `"[1]"` is the
            # string "[1]", not the list `[1]`.
            template = self.env.from_string(template_str)
            result = template.render(enhanced_context)
            return result

        except Exception as e:
            error_msg = (
                f"Template resolution failed for '{template_str}': {e}. "
                f"Available context keys: "
                f"{list(context.keys()) if isinstance(context, dict) else 'N/A'}"
            )
            # Raised, not logged: the exception carries the message, and a
            # caller may handle it (validate(), incremental builds). (R50)
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


class CachingTemplateResolver:
    """Wrapper that adds caching to any TemplateResolver.

    The caches are bounded LRUs (least-recently-used) and guarded by one lock,
    so the wrapper is thread-safe (``AGENTS.md`` AI Guidance §10). Non-string
    inputs bypass the cache and are passed to the wrapped resolver unchanged,
    since a template is always a string; caching them would raise on an
    unhashable input where the wrapped resolver simply returns ``False``.
    """

    def __init__(self, resolver: TemplateResolver, max_cache_size: int = 1000):
        self.resolver = resolver
        self.max_cache_size = max_cache_size
        self._template_cache: OrderedDict[str, bool] = OrderedDict()
        self._variable_cache: OrderedDict[str, Set[str]] = OrderedDict()
        self._lock = threading.Lock()

    def resolve_template(self, template_str: str, context: Dict[str, Any]) -> Any:
        """Resolve template with caching."""
        # For now, simple implementation without context-based caching
        # In production, you might want to cache based on template + context hash
        return self.resolver.resolve_template(template_str, context)

    def is_template(self, value: str) -> bool:
        """Check if string is template with caching."""
        if not isinstance(value, str):
            return self.resolver.is_template(value)

        with self._lock:
            if value in self._template_cache:
                self._template_cache.move_to_end(value)
                return self._template_cache[value]

            result = self.resolver.is_template(value)
            self._template_cache[value] = result
            if len(self._template_cache) > self.max_cache_size:
                self._template_cache.popitem(last=False)
            return result

    def extract_variables(self, template_str: str) -> Set[str]:
        """Extract variables with caching."""
        if not isinstance(template_str, str):
            return self.resolver.extract_variables(template_str)

        with self._lock:
            if template_str in self._variable_cache:
                self._variable_cache.move_to_end(template_str)
                return self._variable_cache[template_str]

            result = self.resolver.extract_variables(template_str)
            self._variable_cache[template_str] = result
            if len(self._variable_cache) > self.max_cache_size:
                self._variable_cache.popitem(last=False)
            return result


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
