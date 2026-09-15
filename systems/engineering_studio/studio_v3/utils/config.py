"""Centralized configuration management"""
import yaml
from pathlib import Path
from typing import Dict, Any

class Config:
    """Configuration management"""

    def __init__(self, config_file: str):
        self.config_file = Path(config_file)
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load YAML config"""
        if self.config_file.exists():
            with open(self.config_file) as f:
                return yaml.safe_load(f) or {}
        return {}

    def get(self, key: str, default=None):
        """Get config value"""
        return self.config.get(key, default)

    def get_nested(self, path: str, default=None):
        """Get nested config value (dot notation)"""
        keys = path.split('.')
        value = self.config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
        return value if value is not None else default

    def set(self, key: str, value: Any):
        """Set config value"""
        self.config[key] = value
        self._save_config()

    def _save_config(self):
        """Save config back to file"""
        with open(self.config_file, 'w') as f:
            yaml.dump(self.config, f)
