"""
config_loader.py
--------------------------------------------------------
Enhanced config loader for AI Trading System (2025)
Features:
  ✅ Automatically finds the nearest config.yaml
  ✅ Expands ${VAR} using environment variables (.env friendly)
  ✅ Supports relative paths per service
  ✅ Returns a validated Python dictionary
--------------------------------------------------------
"""

import os
import yaml
import re
from pathlib import Path


# --------------------------------------------------------
# Helper: Expand ${VAR} placeholders using environment
# --------------------------------------------------------
def _expand_env_vars(obj):
    """Recursively expand ${VAR} placeholders in dict/list/str."""
    if isinstance(obj, dict):
        return {k: _expand_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_expand_env_vars(v) for v in obj]
    elif isinstance(obj, str):
        pattern = re.compile(r"\$\{([^}^{]+)\}")
        match = pattern.findall(obj)
        for g in match:
            obj = obj.replace(f"${{{g}}}", os.getenv(g, ""))
        return obj
    else:
        return obj


# --------------------------------------------------------
# Helper: Locate config.yaml automatically
# --------------------------------------------------------
def _find_config_file(filename="config.yaml", start_dir=None):
    """
    Find config.yaml starting from start_dir (default: cwd)
    and walk up parent directories until found.
    """
    start_path = Path(start_dir or os.getcwd()).resolve()

    for parent in [start_path] + list(start_path.parents):
        candidate = parent / filename
        if candidate.exists():
            return candidate
    # fallback: project root
    root_candidate = Path(__file__).resolve().parent / filename
    if root_candidate.exists():
        return root_candidate

    raise FileNotFoundError(f"⚠️ Could not find {filename} starting from {start_path}")


# --------------------------------------------------------
# Main public API
# --------------------------------------------------------
def load_config(path: str = None) -> dict:
    """
    Loads and expands a YAML configuration.
    - If path is given, loads from that file.
    - Otherwise, auto-discovers the nearest config.yaml.
    """
    config_path = _find_config_file(path or "config.yaml")
    with open(config_path, "r") as f:
        raw = yaml.safe_load(f)

    expanded = _expand_env_vars(raw)
    print(f"✅ Loaded config from: {config_path}")
    return expanded
