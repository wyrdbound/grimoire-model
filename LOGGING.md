# Logging Configuration for Grimoire Model

The `grimoire-model` library uses Python's standard logging module with a centralized logger that applications can configure.

## Quick Setup

The library logger is named `grimoire_model` and all submodules use child loggers under this namespace.

### Basic Configuration

```python
import logging
import sys

# Configure the grimoire-model logger before using the library
grimoire_logger = logging.getLogger('grimoire_model')
grimoire_logger.setLevel(logging.WARNING)  # Only show warnings and errors

# Add a handler to output messages
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
grimoire_logger.addHandler(handler)

# Now import and use the library
from grimoire_model import create_model, ModelDefinition
```

### Using Application-Wide Logging Configuration

If your application already has logging configured, the grimoire-model logger will inherit from your root configuration:

```python
import logging

# Configure your application's root logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Optionally adjust the grimoire-model logger level
logging.getLogger('grimoire_model').setLevel(logging.WARNING)

# Import and use the library
from grimoire_model import create_model, ModelDefinition
```

## Logger Hierarchy

The library uses the following logger hierarchy:

- `grimoire_model` - Root library logger
  - `grimoire_model.core.model` - Model operations
  - `grimoire_model.core.registry` - Model registration and retrieval
  - `grimoire_model.core.schema` - Schema validation
  - `grimoire_model.resolvers.template` - Template resolution
  - `grimoire_model.resolvers.derived` - Derived field computation
  - `grimoire_model.utils.inheritance` - Model inheritance resolution
  - `grimoire_model.validation.validators` - Field validation

## What Gets Logged

The library logs various operational messages:

### Warning Level Messages

- Model registration conflicts: `"Model 'namespace__model_id' already registered. Overwriting with new definition."`
- Template resolution issues
- Validation warnings

### Info Level Messages

- Model creation and registration
- Inheritance resolution results
- Template caching operations

### Debug Level Messages

- Detailed field resolution steps
- Dependency graph computation
- Internal state changes

## Examples

### Suppress All Library Logging

```python
import logging

# Disable all grimoire-model logging
logging.getLogger('grimoire_model').setLevel(logging.CRITICAL)
```

### Log Only Registry Warnings

```python
import logging

# Configure only registry warnings
registry_logger = logging.getLogger('grimoire_model.core.registry')
registry_logger.setLevel(logging.WARNING)
registry_logger.addHandler(logging.StreamHandler())
```

### Detailed Debug Logging

```python
import logging

# Enable debug logging for troubleshooting
logging.getLogger('grimoire_model').setLevel(logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)
```

## Integration with Other Libraries

The grimoire-model logger integrates seamlessly with other logging frameworks:

### With structlog

```python
import structlog
import logging

# Configure structlog
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

# The grimoire-model logger will work with structlog's configuration
```

### With loguru

```python
import sys
from loguru import logger as loguru_logger
import logging

class InterceptHandler(logging.Handler):
    def emit(self, record):
        loguru_logger.opt(depth=6, exception=record.exc_info).log(record.levelname, record.getMessage())

# Intercept grimoire-model logs with loguru
logging.getLogger('grimoire_model').addHandler(InterceptHandler())
```

## Performance Considerations

- The library uses lazy string formatting for log messages (f-strings only evaluated when message will be logged)
- Debug logging may impact performance in high-throughput scenarios
- Consider setting appropriate log levels in production environments

## Accessing the Library Logger

You can also access the library's logger directly:

```python
from grimoire_model import logger, get_logger

# Root library logger
print(f"Library logger: {logger}")

# Get specific submodule logger
registry_logger = get_logger('core.registry')
```

This allows for fine-grained control over logging configuration in your application.
