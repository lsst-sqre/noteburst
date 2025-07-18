"""Constant values for Noteburst."""

from pathlib import Path

__all__ = ["CONFIG_PATH_ENV_VAR", "DEFAULT_CONFIG_PATH"]

CONFIG_PATH_ENV_VAR = "NOTEBURST_CONFIG_PATH"
"""The name of the environment variable containing the config path."""

DEFAULT_CONFIG_PATH = Path("/etc/noteburst/config.yaml")
"""Default path to configuration."""
