# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Updated license from Proprietary to MIT License
- Updated contributing guidelines to welcome open source contributions

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
