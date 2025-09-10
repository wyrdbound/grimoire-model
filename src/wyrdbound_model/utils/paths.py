"""
Path utilities for dot notation access in nested dictionaries.

Provides functions for getting, setting, and manipulating nested values
using dot notation paths (e.g., "character.stats.strength").
"""

from typing import (
    Any,
    Dict,
    List,
)


def get_nested_value(
    data: Dict[str, Any], path: str, default: Any = None, separator: str = "."
) -> Any:
    """Get a nested value from a dictionary using dot notation.

    Args:
        data: The dictionary to access
        path: Dot-separated path to the value (e.g., "stats.strength")
        default: Default value to return if path doesn't exist
        separator: Path separator character (default: ".")

    Returns:
        The value at the specified path, or default if not found

    Examples:
        >>> data = {"stats": {"strength": 15, "dex": 12}}
        >>> get_nested_value(data, "stats.strength")
        15
        >>> get_nested_value(data, "stats.missing", "N/A")
        'N/A'
    """
    if not path:
        return data

    if separator not in path:
        return data.get(path, default)

    keys = path.split(separator)
    current = data

    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]

    return current


def set_nested_value(
    data: Dict[str, Any],
    path: str,
    value: Any,
    separator: str = ".",
    create_missing: bool = True,
) -> None:
    """Set a nested value in a dictionary using dot notation.

    Args:
        data: The dictionary to modify
        path: Dot-separated path to set (e.g., "stats.strength")
        value: Value to set
        separator: Path separator character (default: ".")
        create_missing: Whether to create missing intermediate dictionaries

    Raises:
        KeyError: If create_missing is False and intermediate path doesn't exist
        TypeError: If intermediate path exists but is not a dictionary

    Examples:
        >>> data = {}
        >>> set_nested_value(data, "stats.strength", 15)
        >>> data
        {'stats': {'strength': 15}}
    """
    if not path:
        raise ValueError("Path cannot be empty")

    if separator not in path:
        data[path] = value
        return

    keys = path.split(separator)
    current = data

    # Navigate to the parent of the target key
    for key in keys[:-1]:
        if key not in current:
            if create_missing:
                current[key] = {}
            else:
                raise KeyError(f"Missing intermediate key: {key}")

        if not isinstance(current[key], dict):
            raise TypeError(f"Cannot access key '{key}': value is not a dictionary")

        current = current[key]

    # Set the final value
    current[keys[-1]] = value


def has_nested_value(data: Dict[str, Any], path: str, separator: str = ".") -> bool:
    """Check if a nested path exists in a dictionary.

    Args:
        data: The dictionary to check
        path: Dot-separated path to check (e.g., "stats.strength")
        separator: Path separator character (default: ".")

    Returns:
        True if the path exists, False otherwise

    Examples:
        >>> data = {"stats": {"strength": 15}}
        >>> has_nested_value(data, "stats.strength")
        True
        >>> has_nested_value(data, "stats.missing")
        False
    """
    if not path:
        return True

    if separator not in path:
        return path in data

    keys = path.split(separator)
    current = data

    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return False
        current = current[key]

    return True


def delete_nested_value(data: Dict[str, Any], path: str, separator: str = ".") -> bool:
    """Delete a nested value from a dictionary using dot notation.

    Args:
        data: The dictionary to modify
        path: Dot-separated path to delete (e.g., "stats.strength")
        separator: Path separator character (default: ".")

    Returns:
        True if the value was deleted, False if it didn't exist

    Examples:
        >>> data = {"stats": {"strength": 15, "dex": 12}}
        >>> delete_nested_value(data, "stats.strength")
        True
        >>> data
        {'stats': {'dex': 12}}
    """
    if not path:
        return False

    if separator not in path:
        if path in data:
            del data[path]
            return True
        return False

    keys = path.split(separator)
    current = data

    # Navigate to the parent of the target key
    for key in keys[:-1]:
        if not isinstance(current, dict) or key not in current:
            return False
        current = current[key]

    # Delete the final key if it exists
    final_key = keys[-1]
    if isinstance(current, dict) and final_key in current:
        del current[final_key]
        return True

    return False


def flatten_dict(
    data: Dict[str, Any], separator: str = ".", prefix: str = ""
) -> Dict[str, Any]:
    """Flatten a nested dictionary into dot-notation keys.

    Args:
        data: The dictionary to flatten
        separator: Path separator character (default: ".")
        prefix: Prefix to add to all keys

    Returns:
        Flattened dictionary with dot-notation keys

    Examples:
        >>> data = {"stats": {"strength": 15, "dex": 12}}
        >>> flatten_dict(data)
        {'stats.strength': 15, 'stats.dex': 12}
    """
    result = {}

    for key, value in data.items():
        new_key = f"{prefix}{separator}{key}" if prefix else key

        if isinstance(value, dict):
            result.update(flatten_dict(value, separator, new_key))
        else:
            result[new_key] = value

    return result


def unflatten_dict(data: Dict[str, Any], separator: str = ".") -> Dict[str, Any]:
    """Unflatten a dictionary with dot-notation keys into nested structure.

    Args:
        data: The flattened dictionary
        separator: Path separator character (default: ".")

    Returns:
        Nested dictionary

    Examples:
        >>> data = {'stats.strength': 15, 'stats.dex': 12}
        >>> unflatten_dict(data)
        {'stats': {'strength': 15, 'dex': 12}}
    """
    result: Dict[str, Any] = {}

    for key, value in data.items():
        set_nested_value(result, key, value, separator)

    return result


def merge_nested_dicts(
    target: Dict[str, Any], source: Dict[str, Any], overwrite: bool = True
) -> Dict[str, Any]:
    """Recursively merge two nested dictionaries.

    Args:
        target: Target dictionary to merge into
        source: Source dictionary to merge from
        overwrite: Whether to overwrite existing values

    Returns:
        Merged dictionary (modifies target in-place)

    Examples:
        >>> target = {"stats": {"strength": 15}}
        >>> source = {"stats": {"dex": 12}, "name": "Hero"}
        >>> merge_nested_dicts(target, source)
        {'stats': {'strength': 15, 'dex': 12}, 'name': 'Hero'}
    """
    for key, value in source.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            # Recursively merge nested dictionaries
            merge_nested_dicts(target[key], value, overwrite)
        elif overwrite or key not in target:
            # Set the value (overwrite or new key)
            target[key] = value

    return target


def get_nested_paths(
    data: Dict[str, Any], separator: str = ".", include_intermediate: bool = False
) -> List[str]:
    """Get all nested paths in a dictionary.

    Args:
        data: The dictionary to analyze
        separator: Path separator character (default: ".")
        include_intermediate: Whether to include intermediate dictionary paths

    Returns:
        List of all paths in the dictionary

    Examples:
        >>> data = {"stats": {"strength": 15, "dex": 12}}
        >>> get_nested_paths(data)
        ['stats.strength', 'stats.dex']
        >>> get_nested_paths(data, include_intermediate=True)
        ['stats', 'stats.strength', 'stats.dex']
    """
    paths = []

    def _collect_paths(current_data: Dict[str, Any], prefix: str = "") -> None:
        for key, value in current_data.items():
            current_path = f"{prefix}{separator}{key}" if prefix else key

            if isinstance(value, dict):
                if include_intermediate:
                    paths.append(current_path)
                _collect_paths(value, current_path)
            else:
                paths.append(current_path)

    _collect_paths(data)
    return sorted(paths)


def filter_dict_by_paths(
    data: Dict[str, Any], paths: List[str], separator: str = "."
) -> Dict[str, Any]:
    """Filter a dictionary to only include specified paths.

    Args:
        data: The dictionary to filter
        paths: List of paths to include
        separator: Path separator character (default: ".")

    Returns:
        New dictionary containing only the specified paths

    Examples:
        >>> data = {"stats": {"strength": 15, "dex": 12}, "name": "Hero"}
        >>> filter_dict_by_paths(data, ["stats.strength", "name"])
        {'stats': {'strength': 15}, 'name': 'Hero'}
    """
    result: Dict[str, Any] = {}

    for path in paths:
        if has_nested_value(data, path, separator):
            value = get_nested_value(data, path, separator=separator)
            set_nested_value(result, path, value, separator)

    return result
