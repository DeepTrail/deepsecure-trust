'''Utility functions for DeepSecure CLI.'''

import uuid
import json
import string
import random
from typing import Any, Dict, Optional, Union
from datetime import datetime
from pydantic import BaseModel
import logging
import sys
from functools import wraps
import functools

try:
    import typer
except ImportError:
    typer = None  # type: ignore[assignment]

try:
    from rich.console import Console
    from rich.syntax import Syntax
    from rich.theme import Theme
    from rich.logging import RichHandler
    from rich.panel import Panel
    _HAS_RICH = True
except ImportError:
    Console = None  # type: ignore[assignment,misc]
    Syntax = None  # type: ignore[assignment,misc]
    Theme = None  # type: ignore[assignment,misc]
    RichHandler = None  # type: ignore[assignment,misc]
    Panel = None  # type: ignore[assignment,misc]
    _HAS_RICH = False

from .exceptions import DeepSecureClientError, DeepSecureError

# Central console objects for consistent output
class _FallbackConsole:
    """Minimal console stand-in when Rich is not installed."""

    def print(self, *args, **kwargs):
        style = kwargs.pop("style", "")
        text = " ".join(str(a) for a in args)
        import re
        text = re.sub(r"\[/?[a-z_ ]+\]", "", text)
        dest = sys.stderr if "error" in style or "red" in style else sys.stdout
        print(text, file=dest)


if _HAS_RICH:
    console = Console()
    error_console = Console(stderr=True, style="bold red")
    custom_theme = Theme({
        "info": "dim cyan",
        "warning": "magenta",
        "error": "bold red",
        "success": "bold green",
        "debug": "dim blue"
    })
    console = Console(theme=custom_theme)
else:
    console = _FallbackConsole()  # type: ignore[assignment]
    error_console = _FallbackConsole()  # type: ignore[assignment]

# --- Logging Setup --- #
DEFAULT_LOG_LEVEL = "WARNING" # Default if not configured

# Store the original stdout/stderr for direct printing if needed - REMOVED
# _original_stdout = sys.stdout
# _original_stderr = sys.stderr

def setup_logging(level_str: Optional[str] = None):
    """Configures logging for the CLI application using RichHandler.

    Args:
        level_str: The desired logging level as a string (e.g., "DEBUG", "INFO").
                   If None, defaults to DEFAULT_LOG_LEVEL.
    """
    log_level_to_set = (level_str or DEFAULT_LOG_LEVEL).upper()
    numeric_level = getattr(logging, log_level_to_set, None)

    if not isinstance(numeric_level, int):
        print(f"Invalid log level '{log_level_to_set}'. Falling back to {DEFAULT_LOG_LEVEL}.", file=sys.stderr)
        log_level_to_set = DEFAULT_LOG_LEVEL
        numeric_level = getattr(logging, log_level_to_set)

    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

    handlers: list = []
    if _HAS_RICH and RichHandler and console:
        handlers.append(RichHandler(console=console, rich_tracebacks=True, markup=True))
    else:
        handlers.append(logging.StreamHandler())

    logging.basicConfig(
        level=numeric_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=handlers,
    )

    logging.getLogger("deepsecure.core.vault_client").setLevel(numeric_level)

    # You can also set levels for specific loggers if needed:
    # logging.getLogger("deepsecure").setLevel(numeric_level)
    # logging.getLogger("httpx").setLevel(logging.WARNING) # Example: quiet noisy library

    # console.print(f"[DEBUG] Logging initialized with level: {log_level_to_set} ({numeric_level})", style="debug") # For verifying setup

def print_success(message: str):
    """Prints a success message to the console."""
    if _HAS_RICH:
        console.print(Panel(f"✅ {message}", style="bold green", expand=False))
    else:
        console.print(f"OK: {message}")

def print_error(message: str, exit_code: Optional[int] = None):
    """Prints a formatted error message to stderr and optionally exits."""
    console.print(f"❌ Error: {message}", style="error")

def print_warning(message: str):
    """Prints a formatted warning message to the console."""
    console.print(f"⚠️ Warning: {message}", style="warning")

def print_info(message: str):
    console.print(f"ℹ️ Info: {message}", style="info")

def print_debug(message: str):
    logging.getLogger("deepsecure.cli").debug(message)

def print_json(data: Union[Dict[str, Any], BaseModel], pretty: bool = True):
    """
    Prints dictionary or Pydantic model data as formatted JSON.
    
    Args:
        data: The dictionary or Pydantic model to print.
        pretty: If True (default), indent the JSON for readability.
    """
    indent = 2 if pretty else None
    json_str = ""
    try:
        if isinstance(data, BaseModel):
            json_str = data.model_dump_json(indent=indent)
        elif isinstance(data, dict):
            json_str = json.dumps(data, indent=indent, sort_keys=True, ensure_ascii=False, default=str)
        else:
            json_str = json.dumps(data, indent=indent, sort_keys=True, ensure_ascii=False, default=str)

        # Use current sys.stdout for JSON to ensure it's clean for piping
        # This bypasses Rich console styling and ensures CliRunner captures it.
        sys.stdout.write(json_str + "\n")
        sys.stdout.flush()
    except (TypeError, ValueError) as e:
        error_console.print(f"Error: Failed to format data as JSON: {e}", style="error")

def generate_id(length: int = 8) -> str:
    """
    Generate a short, random, lowercase alphanumeric ID string.

    Useful for creating simple identifiers for temporary resources.
    
    Args:
        length: The desired length of the ID string (default: 8).
        
    Returns:
        A random lowercase alphanumeric string of the specified length.
    """
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def format_timestamp(timestamp: Optional[int], format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Format a Unix timestamp as a human-readable date/time string.

    Handles None input gracefully by returning a placeholder.
    
    Args:
        timestamp: The Unix timestamp (integer seconds since epoch), or None.
        format_str: The format string compatible with `strftime`.
        
    Returns:
        The formatted date/time string, or "N/A" if timestamp is None.
    """
    if timestamp is None:
        return "N/A"
    try:
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime(format_str)
    except (ValueError, OSError, TypeError):
        # Handle potential errors with invalid timestamps
        return f"Invalid timestamp ({timestamp})"

def parse_ttl_to_seconds(ttl_str: str) -> int:
    """Parses a TTL string (e.g., '5m', '1h', '7d') into seconds.

    Supported suffixes: s (seconds), m (minutes), h (hours), d (days), w (weeks).
    If no suffix, assumes seconds.

    Args:
        ttl_str: The TTL string to parse.

    Returns:
        The TTL in seconds as an integer.

    Raises:
        ValueError: If the TTL format is invalid or suffix is unsupported.
    """
    ttl_str = ttl_str.strip().lower()
    if not ttl_str:
        raise ValueError("TTL string cannot be empty.")

    num_part = ''
    unit_part = ''

    for char in ttl_str:
        if char.isdigit() or (char == '.' and '.' not in num_part):
            num_part += char
        else:
            unit_part += char
            
    if not num_part:
        raise ValueError(f"Invalid TTL format: '{ttl_str}'. No numeric part found.")

    try:
        value = float(num_part) # Use float to allow for e.g. 0.5h
    except ValueError:
        raise ValueError(f"Invalid TTL numeric value: '{num_part}' in '{ttl_str}'.")

    if not unit_part or unit_part == 's':
        multiplier = 1
    elif unit_part == 'm':
        multiplier = 60
    elif unit_part == 'h':
        multiplier = 3600
    elif unit_part == 'd':
        multiplier = 86400
    elif unit_part == 'w':
        multiplier = 604800
    else:
        raise ValueError(f"Invalid TTL unit: '{unit_part}' in '{ttl_str}'. Supported units: s, m, h, d, w.")
    
    total_seconds = value * multiplier
    if total_seconds <= 0:
        raise ValueError(f"TTL must be positive. Calculated {total_seconds}s from '{ttl_str}'.")
    
    return int(total_seconds)

def get_client():
    """
    Creates and returns a DeepSecure client instance.
    
    This is a convenience function for commands that need a client.
    It handles the import and instantiation in one place.
    
    Returns:
        A configured DeepSecure Client instance.
    """
    # Import here to avoid circular imports
    from .client import Client
    return Client()

def handle_api_error(func):
    """Decorator to catch and handle API errors gracefully."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except DeepSecureClientError as e:
            print_error(f"API Error: {e}")
            if typer:
                raise typer.Exit(code=1)
            sys.exit(1)
        except DeepSecureError as e:
            print_error(f"A general error occurred: {e}")
            if typer:
                raise typer.Exit(code=1)
            sys.exit(1)
        except Exception as e:
            print_error(f"An unexpected error occurred: {e}")
            if typer:
                raise typer.Exit(code=1)
            sys.exit(1)
    return wrapper

# TODO: Add more utility functions as needed (e.g., table rendering, file handling). 