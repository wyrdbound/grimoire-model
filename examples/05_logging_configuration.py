#!/usr/bin/env python3
"""
Example 05: Logging Configuration

This example demonstrates how to configure logging for the grimoire-model library
using grimoire-logging's dependency injection capabilities.
"""

import json
import logging
import sys
from datetime import datetime

from grimoire_model import (
    AttributeDefinition,
    ModelDefinition,
    create_model,
    inject_logger,
    clear_logger_injection,
    register_model,
)


def example_basic_logging_setup():
    """Example 1: Basic logging setup with standard Python logging."""
    print("=== Example 1: Basic Standard Logging Setup ===")

    # Configure standard Python logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    # Create a model to see logging in action
    character_def = ModelDefinition(
        id="character",
        name="Player Character",
        attributes={
            "name": AttributeDefinition(type="str", required=True),
            "level": AttributeDefinition(type="int", default=1),
            "hp": AttributeDefinition(type="int", derived="{{ level * 8 }}"),
        }
    )

    # This will log model creation
    character = create_model(character_def, {"name": "Aragorn", "level": 5})
    print(f"Character HP: {character['hp']}")

    # Register model (will show debug logs if level is set to DEBUG)
    register_model("examples", character_def)
    print()


def example_custom_logger():
    """Example 2: Using a custom logger with grimoire-logging."""
    print("=== Example 2: Custom Logger Implementation ===")

    class CustomLogger:
        """Custom logger that adds emojis to log messages."""

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

    # Inject our custom logger
    inject_logger(CustomLogger())

    # Create a model - now using custom logger
    weapon_def = ModelDefinition(
        id="weapon",
        name="Weapon",
        attributes={
            "name": AttributeDefinition(type="str", required=True),
            "damage": AttributeDefinition(type="int", default=1),
            "durability": AttributeDefinition(type="int", default=100),
            "condition": AttributeDefinition(
                type="str",
                derived="{{ 'Broken' if durability <= 0 else 'Good' if durability > 50 else 'Worn' }}"
            ),
        }
    )

    sword = create_model(weapon_def, {"name": "Sting", "damage": 10, "durability": 75})
    print(f"Weapon condition: {sword['condition']}")

    # Clear custom logger
    clear_logger_injection()
    print()


def example_structured_json_logger():
    """Example 3: Structured JSON logging."""
    print("=== Example 3: Structured JSON Logging ===")

    class JSONLogger:
        """Logger that outputs structured JSON logs."""

        def _log(self, level: str, message: str) -> None:
            log_entry = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": level,
                "logger": "grimoire_model",
                "message": message
            }
            print(json.dumps(log_entry))

        def debug(self, msg: str, *args, **kwargs) -> None:
            self._log("DEBUG", msg)

        def info(self, msg: str, *args, **kwargs) -> None:
            self._log("INFO", msg)

        def warning(self, msg: str, *args, **kwargs) -> None:
            self._log("WARNING", msg)

        def error(self, msg: str, *args, **kwargs) -> None:
            self._log("ERROR", msg)

        def critical(self, msg: str, *args, **kwargs) -> None:
            self._log("CRITICAL", msg)

    # Use JSON logger
    inject_logger(JSONLogger())

    # Create a model with some complex derived fields
    spell_def = ModelDefinition(
        id="spell",
        name="Spell",
        attributes={
            "name": AttributeDefinition(type="str", required=True),
            "level": AttributeDefinition(type="int", default=1),
            "school": AttributeDefinition(type="str", default="Evocation"),
            "mana_cost": AttributeDefinition(type="int", derived="{{ level * 5 }}"),
            "damage": AttributeDefinition(type="int", derived="{{ level * 6 + 4 }}"),
            "description": AttributeDefinition(
                type="str",
                derived="{{ 'A level ' + level|string + ' ' + school|lower + ' spell dealing ' + damage|string + ' damage for ' + mana_cost|string + ' mana' }}"
            ),
        }
    )

    fireball = create_model(spell_def, {"name": "Fireball", "level": 3, "school": "Evocation"})
    print(f"Spell description (non-JSON): {fireball['description']}")

    clear_logger_injection()
    print()


def example_filtering_logger():
    """Example 4: Logger with filtering capabilities."""
    print("=== Example 4: Filtering Logger ===")

    class FilteringLogger:
        """Logger that filters messages based on content."""

        def __init__(self, min_level: str = "INFO", exclude_patterns: list[str] | None = None):
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

        def _log(self, level: str, message: str) -> None:
            if self._should_log(level, message):
                print(f"[{level}] {message}")

        def debug(self, msg: str, *args, **kwargs) -> None:
            self._log("DEBUG", msg)

        def info(self, msg: str, *args, **kwargs) -> None:
            self._log("INFO", msg)

        def warning(self, msg: str, *args, **kwargs) -> None:
            self._log("WARNING", msg)

        def error(self, msg: str, *args, **kwargs) -> None:
            self._log("ERROR", msg)

        def critical(self, msg: str, *args, **kwargs) -> None:
            self._log("CRITICAL", msg)

    # Use filtering logger - only show WARNING and above, exclude certain patterns
    inject_logger(FilteringLogger(min_level="WARNING", exclude_patterns=["derived field"]))

    # Create models that would normally generate debug logs
    item_def = ModelDefinition(
        id="item",
        name="Item",
        attributes={
            "name": AttributeDefinition(type="str", required=True),
            "value": AttributeDefinition(type="int", default=1),
            "weight": AttributeDefinition(type="float", default=0.1),
            "value_per_weight": AttributeDefinition(type="float", derived="{{ value / weight }}"),
        }
    )

    # This should show warnings but not debug messages
    gem = create_model(item_def, {"name": "Ruby", "value": 100, "weight": 0.05})
    print(f"Value per weight: {gem['value_per_weight']}")

    # Try to register a model with the same ID (should show warning)
    register_model("examples", item_def)
    register_model("examples", item_def)  # This should trigger a warning

    clear_logger_injection()
    print()


def example_integration_with_standard_logging():
    """Example 5: Integration with existing standard logging setup."""
    print("=== Example 5: Integration with Standard Logging ===")

    # Set up standard logging with a custom formatter
    logger = logging.getLogger("myapp")
    logger.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        '%(asctime)s | %(name)s | %(levelname)-8s | %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Create an adapter to integrate grimoire-model with existing logging
    class StandardLoggingAdapter:
        """Adapter to use standard Python logging as the backend."""

        def __init__(self, logger_name: str = "grimoire_model"):
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

    # Configure grimoire-model to use our standard logging setup
    inject_logger(StandardLoggingAdapter("myapp.grimoire_model"))

    # Now grimoire-model logs will appear in our application's logging system
    print("Creating model with integrated logging...")

    npc_def = ModelDefinition(
        id="npc",
        name="NPC",
        attributes={
            "name": AttributeDefinition(type="str", required=True),
            "level": AttributeDefinition(type="int", default=1),
            "health": AttributeDefinition(type="int", derived="{{ level * 10 + 20 }}"),
            "challenge_rating": AttributeDefinition(type="float", derived="{{ level * 0.5 }}"),
        }
    )

    npc = create_model(npc_def, {"name": "Goblin Warrior", "level": 2})
    print(f"NPC Health: {npc['health']}, Challenge Rating: {npc['challenge_rating']}")

    clear_logger_injection()
    print()


def main():
    """Run all logging configuration examples."""
    print("Grimoire Model - Logging Configuration Examples")
    print("=" * 50)
    print()

    example_basic_logging_setup()
    example_custom_logger()
    example_structured_json_logger()
    example_filtering_logger()
    example_integration_with_standard_logging()

    print("All examples completed!")


if __name__ == "__main__":
    main()
