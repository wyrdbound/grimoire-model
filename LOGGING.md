# Logging Configuration for Grimoire Model

The `grimoire-model` library uses `grimoire-logging` for flexible logging with dependency injection capabilities. This allows you to easily inject custom logger implementations or use standard Python logging.

## Quick Setup

The library uses the logger namespace `grimoire_model` with child loggers for different components. You can configure logging in several ways:

### Method 1: Standard Python Logging (Default)

By default, grimoire-model falls back to Python's standard logging. Configure it before importing the library:

```python
import logging
import sys

# Configure standard logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Optionally adjust the grimoire-model logger level
logging.getLogger('grimoire_model').setLevel(logging.DEBUG)

# Now import and use the library
from grimoire_model import create_model, ModelDefinition
```

### Method 2: Dependency Injection with Custom Logger

Use grimoire-logging's dependency injection to provide your own logger implementation:

```python
from grimoire_model import inject_logger, create_model, ModelDefinition

# Create a custom logger
class MyCustomLogger:
    def debug(self, msg: str, *args, **kwargs) -> None:
        print(f"🐛 DEBUG: {msg}")

    def info(self, msg: str, *args, **kwargs) -> None:
        print(f"📝 INFO: {msg}")

    def warning(self, msg: str, *args, **kwargs) -> None:
        print(f"⚠️ WARNING: {msg}")

    def error(self, msg: str, *args, **kwargs) -> None:
        print(f"❌ ERROR: {msg}")

    def critical(self, msg: str, *args, **kwargs) -> None:
        print(f"💀 CRITICAL: {msg}")

# Inject your custom logger
inject_logger(MyCustomLogger())

# All grimoire-model logging now uses your custom logger
model = create_model(my_definition, my_data)
```

### Method 3: Adapter Pattern for Integration

Create an adapter to integrate with your existing logging infrastructure:

```python
import logging
from grimoire_model import inject_logger

class StandardLoggingAdapter:
    """Adapter to use your existing Python logging setup."""

    def __init__(self, logger_name: str = "myapp.grimoire_model"):
        self.logger = logging.getLogger(logger_name)

    def debug(self, msg: str, *args, **kwargs) -> None:
        self.logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs) -> None:
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs) -> None:
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:
        self.logger.error(msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs) -> None:
        self.logger.critical(msg, *args, **kwargs)

# Use your existing logging configuration
inject_logger(StandardLoggingAdapter())
```

## Logger Hierarchy

The library uses the following logger hierarchy (all under the `grimoire_model` namespace):

- `grimoire_model` - Root library logger
- `grimoire_model.core.model` - Model operations and lifecycle
- `grimoire_model.core.registry` - Model registration and retrieval
- `grimoire_model.resolvers.template` - Template resolution for derived fields
- `grimoire_model.resolvers.derived` - Derived field computation and dependency management
- `grimoire_model.utils.inheritance` - Model inheritance resolution

## What Gets Logged

The library logs messages at appropriate levels for different operational scenarios:

### INFO Level Messages

- **Model Creation**: `"Successfully initialized model 'model_id' with instance ID 'uuid'"`
- **Setup Confirmation**: Indicates successful model initialization and configuration

### WARNING Level Messages

- **Model Registration Conflicts**: `"Model 'namespace__model_id' already registered. Overwriting with new definition."`
- **Template Resolution Issues**: When template variables cannot be resolved
- **Validation Warnings**: Non-fatal validation issues

### DEBUG Level Messages

- **Model Registration**: `"Registered model 'model_id' in namespace 'namespace'"`
- **Model Unregistration**: `"Unregistered model 'namespace__model_id'"`
- **Registry Operations**: `"Cleared N models from namespace 'namespace'"`
- **Derived Field Setup**: `"Registering derived field: field_name = {{ expression }}"`
- **Dependency Tracking**: `"Dependencies for field_name: {dependencies}"`
- **Field Computation**: `"Computed derived field field_name = value"`
- **Field Updates**: `"Field updated: field_name old_value -> new_value"`
- **Default Application**: `"Applied default value for 'field_name': default_value"`

### ERROR Level Messages

- **Template Errors**: Failed template resolution with detailed error information
- **Observer Errors**: Errors in derived field observers during computation

## Configuration Examples

### Suppress All Library Logging

```python
from grimoire_model import inject_logger

# Option 1: Use a null logger
class NullLogger:
    def debug(self, msg, *args, **kwargs): pass
    def info(self, msg, *args, **kwargs): pass
    def warning(self, msg, *args, **kwargs): pass
    def error(self, msg, *args, **kwargs): pass
    def critical(self, msg, *args, **kwargs): pass

inject_logger(NullLogger())

# Option 2: Set standard logging to critical level
import logging
logging.getLogger('grimoire_model').setLevel(logging.CRITICAL)
```

### Structured JSON Logging

```python
import json
from datetime import datetime
from grimoire_model import inject_logger

class JSONLogger:
    def _log(self, level: str, message: str):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "logger": "grimoire_model",
            "message": message
        }
        print(json.dumps(log_entry))

    def debug(self, msg: str, *args, **kwargs): self._log("DEBUG", msg)
    def info(self, msg: str, *args, **kwargs): self._log("INFO", msg)
    def warning(self, msg: str, *args, **kwargs): self._log("WARNING", msg)
    def error(self, msg: str, *args, **kwargs): self._log("ERROR", msg)
    def critical(self, msg: str, *args, **kwargs): self._log("CRITICAL", msg)

inject_logger(JSONLogger())
```

### Filtering Logger

```python
from grimoire_model import inject_logger

class FilteringLogger:
    def __init__(self, min_level="INFO", exclude_patterns=None):
        self.levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        self.min_level_index = self.levels.index(min_level.upper())
        self.exclude_patterns = exclude_patterns or []

    def _should_log(self, level: str, message: str) -> bool:
        level_index = self.levels.index(level.upper())
        if level_index < self.min_level_index:
            return False
        for pattern in self.exclude_patterns:
            if pattern in message:
                return False
        return True

    def _log(self, level: str, message: str):
        if self._should_log(level, message):
            print(f"[{level}] {message}")

    def debug(self, msg: str, *args, **kwargs): self._log("DEBUG", msg)
    def info(self, msg: str, *args, **kwargs): self._log("INFO", msg)
    def warning(self, msg: str, *args, **kwargs): self._log("WARNING", msg)
    def error(self, msg: str, *args, **kwargs): self._log("ERROR", msg)
    def critical(self, msg: str, *args, **kwargs): self._log("CRITICAL", msg)

# Only show warnings and above, exclude derived field messages
inject_logger(FilteringLogger(min_level="WARNING", exclude_patterns=["derived field"]))
```

### Detailed Debug Logging

```python
import logging

# Enable debug logging for troubleshooting
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# No need to inject a logger - uses standard logging by default
# Now all DEBUG messages will be shown
```

## Integration with Other Libraries

Grimoire-model's logging system integrates seamlessly with popular logging frameworks through dependency injection:

### With structlog

```python
import structlog
from grimoire_model import inject_logger

# Configure structlog
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

class StructlogAdapter:
    def __init__(self):
        self.logger = structlog.get_logger("grimoire_model")

    def debug(self, msg: str, *args, **kwargs): self.logger.debug(msg)
    def info(self, msg: str, *args, **kwargs): self.logger.info(msg)
    def warning(self, msg: str, *args, **kwargs): self.logger.warning(msg)
    def error(self, msg: str, *args, **kwargs): self.logger.error(msg)
    def critical(self, msg: str, *args, **kwargs): self.logger.critical(msg)

inject_logger(StructlogAdapter())
```

### With loguru

```python
from loguru import logger
from grimoire_model import inject_logger

class LoguruAdapter:
    def debug(self, msg: str, *args, **kwargs): logger.debug(msg)
    def info(self, msg: str, *args, **kwargs): logger.info(msg)
    def warning(self, msg: str, *args, **kwargs): logger.warning(msg)
    def error(self, msg: str, *args, **kwargs): logger.error(msg)
    def critical(self, msg: str, *args, **kwargs): logger.critical(msg)

inject_logger(LoguruAdapter())
```

### With Rich Console

```python
from rich.console import Console
from grimoire_model import inject_logger

class RichConsoleLogger:
    def __init__(self):
        self.console = Console()

    def debug(self, msg: str, *args, **kwargs):
        self.console.print(f"[dim]DEBUG: {msg}[/dim]")

    def info(self, msg: str, *args, **kwargs):
        self.console.print(f"[blue]INFO: {msg}[/blue]")

    def warning(self, msg: str, *args, **kwargs):
        self.console.print(f"[yellow]WARNING: {msg}[/yellow]")

    def error(self, msg: str, *args, **kwargs):
        self.console.print(f"[red]ERROR: {msg}[/red]")

    def critical(self, msg: str, *args, **kwargs):
        self.console.print(f"[bold red]CRITICAL: {msg}[/bold red]")

inject_logger(RichConsoleLogger())
```

## Advanced Configuration

### Thread-Safe Logger Management

```python
import threading
from grimoire_model import inject_logger, get_logger

def worker_function(worker_id):
    logger = get_logger(f"worker_{worker_id}")
    logger.info(f"Worker {worker_id} starting")
    # All workers use the same injected logger
    logger.info(f"Worker {worker_id} finished")

# Inject logger once - all threads will use it
inject_logger(MyCustomLogger())

# Start multiple threads
threads = [threading.Thread(target=worker_function, args=(i,)) for i in range(5)]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()
```

### Runtime Logger Switching

```python
from grimoire_model import inject_logger, clear_logger_injection

# Start with custom logger
inject_logger(CustomLogger())
# ... use library ...

# Switch to JSON logger
inject_logger(JSONLogger())
# ... different logging format ...

# Revert to standard logging
clear_logger_injection()
# ... back to default behavior ...
```

### Accessing Individual Loggers

```python
from grimoire_model import get_logger

# Get loggers for specific subsystems
model_logger = get_logger('core.model')
registry_logger = get_logger('core.registry')
derived_logger = get_logger('resolvers.derived')

# These all respect the injected logger configuration
model_logger.info("Model-specific message")
registry_logger.debug("Registry-specific debug")
```

## Performance Considerations

- **Lazy Evaluation**: Log messages use f-strings and are only evaluated when the message will actually be logged
- **Debug Impact**: Extensive debug logging (especially derived field computation) may impact performance in high-throughput scenarios
- **Production Settings**: Consider using WARNING or ERROR level in production environments
- **Custom Loggers**: Custom logger implementations should be efficient as they're called frequently during model operations

## Examples and Testing

See `examples/05_logging_configuration.py` for comprehensive examples demonstrating:

- Basic standard logging setup
- Custom logger implementations
- Structured JSON logging
- Message filtering
- Integration with existing logging infrastructure

For testing scenarios, you can easily inject a mock logger:

```python
from grimoire_model import inject_logger, clear_logger_injection

class MockLogger:
    def __init__(self):
        self.messages = []

    def debug(self, msg, *args, **kwargs):
        self.messages.append(('DEBUG', msg))

    def info(self, msg, *args, **kwargs):
        self.messages.append(('INFO', msg))

    # ... other methods ...

# In your tests
mock_logger = MockLogger()
inject_logger(mock_logger)
# ... run your test code ...
assert any('Successfully initialized model' in msg for level, msg in mock_logger.messages)
clear_logger_injection()  # Clean up
```

## API Reference

### Core Functions

- **`inject_logger(logger)`**: Inject a custom logger implementation
- **`clear_logger_injection()`**: Revert to standard Python logging
- **`get_logger(name)`**: Get a logger for a specific subsystem
- **`logger`**: The root grimoire_model logger instance

### Logger Protocol

Custom loggers must implement:

- `debug(msg: str, *args, **kwargs) -> None`
- `info(msg: str, *args, **kwargs) -> None`
- `warning(msg: str, *args, **kwargs) -> None`
- `error(msg: str, *args, **kwargs) -> None`
- `critical(msg: str, *args, **kwargs) -> None`
