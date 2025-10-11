# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.2] - 2025-10-10

### Fixed

- **Nested Model Instantiation**: Fixed nested model types not being automatically instantiated as GrimoireModel objects
  - Custom model types in AttributeDefinition (e.g., `type="stat"`) are now recursively instantiated as GrimoireModel objects
  - Derived fields in nested models are computed correctly at all nesting depths
  - Template resolution now works properly with custom model types at any nesting depth (e.g., `{{ abilities.constitution.bonus }}`)
  - Namespace resolution works across nested models, supporting both same-namespace and cross-namespace references
  - Added comprehensive test coverage for 2-level and 3-level nesting scenarios

## [0.2.1] - 2025-10-01

### Added

- **Dict Type Inference**: Automatic inference of `type: dict` for nested attribute structures
  - When an attribute definition contains nested dictionaries with at least one having a `type` field, the parent attribute automatically infers `type: dict`
  - Allows intuitive nested attribute definitions like:
    ```yaml
    hit_points:
      max: { type: int }
      current: { type: int, range: "0..{{ this.hit_points.max }}" }
    ```
  - Works recursively for deeply nested structures
  - Explicit type declarations always take precedence
  - Empty dicts and dicts without typed nested attributes still require explicit `type` field

## [0.2.0] - 2025-09-12

### Changed

- **BREAKING**: Replaced internal logging system with grimoire-logging for flexible dependency injection
- Updated logging architecture to use grimoire-logging's LoggerProtocol and dependency injection
- Enhanced logging with appropriate INFO, DEBUG, WARNING, and ERROR level messages throughout the system
- Updated license from Proprietary to MIT License
- Updated contributing guidelines to welcome open source contributions

### Added

- Dependency on grimoire-logging package (>=0.1.0) for flexible logging capabilities
- New logging configuration examples (examples/05_logging_configuration.py) demonstrating:
  - Standard Python logging integration
  - Custom logger implementations with emojis and formatting
  - Structured JSON logging for modern logging systems
  - Message filtering and level management
  - Integration patterns with existing logging infrastructure
- Comprehensive logging documentation in LOGGING.md with:
  - Multiple configuration approaches (standard logging, dependency injection, adapters)
  - Integration examples for popular logging frameworks (structlog, loguru, rich)
  - Thread-safe logging management patterns
  - Performance considerations and best practices
- INFO level logging for successful model initialization
- Enhanced DEBUG logging for model registration, derived field computation, and system operations
- Support for runtime logger switching and configuration
- Thread-safe logger management capabilities

### Removed

- Legacy utils/logging.py module (replaced by grimoire-logging integration)

### Technical Changes

- Logger instances now use LoggerProtocol from grimoire-logging
- All logging calls updated to work with grimoire-logging's dependency injection system
- Added inject_logger and clear_logger_injection functions to public API
- Logging namespace remains 'grimoire_model' with hierarchical child loggers

## [0.1.0] - 2025-09-11

### Added

- Initial release of Grimoire Model system
- Dict-like interface with schema validation using Pydantic
- Reactive derived fields with automatic dependency tracking
- Model inheritance system with multiple inheritance support
- Template expressions using Jinja2 for dynamic field content
- Namespace-based model organization and global registry
- Custom validation rules and field validators
- Dependency injection system with pluggable resolvers
- Performance optimizations with batch updates and lazy evaluation
- Comprehensive logging system with configurable levels
- Template resolver for Jinja2-based field expressions
- Derived resolver for automatic field computation
- Path-based utilities for nested data access
- Exception handling with detailed error messages
- Support for Python 3.8+ with type hints
- Complete test suite with high coverage
- Documentation with examples and API reference
- Integration with grimoire-context for game state management

### Technical Features

- Pyrsistent-based immutable data structures
- Thread-safe operations
- YAML configuration support
- Comprehensive error handling and validation
- Modular architecture with pluggable components
