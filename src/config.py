"""
Configuration loader and validator for the Face Analytics module.
"""

from pathlib import Path
from typing import Any, Dict
import yaml


def get_project_root() -> Path:
    """Returns the absolute root directory of the project."""
    return Path(__file__).resolve().parent.parent


def load_config(config_path: str | Path | None = None) -> Dict[str, Any]:
    """Loads configuration from YAML file and resolves filesystem paths."""
    root = get_project_root()
    if config_path is None:
        config_path = root / "configs" / "config.yaml"
    else:
        config_path = Path(config_path)
        if not config_path.is_absolute():
            config_path = root / config_path

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found at: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # Helper to resolve relative paths
    def resolve_path(p: str) -> Path:
        path_obj = Path(p)
        return path_obj if path_obj.is_absolute() else (root / path_obj).resolve()

    # Resolve filesystem paths inside cfg
    if "models" in cfg:
        cfg["models"]["detector_path"] = str(resolve_path(cfg["models"]["detector_path"]))
        cfg["models"]["recognizer_path"] = str(resolve_path(cfg["models"]["recognizer_path"]))

    if "recognition" in cfg:
        cfg["recognition"]["gallery_path"] = str(resolve_path(cfg["recognition"]["gallery_path"]))
        cfg["recognition"]["gallery_manifest_path"] = str(resolve_path(cfg["recognition"]["gallery_manifest_path"]))

    if "events" in cfg:
        cfg["events"]["events_log_path"] = str(resolve_path(cfg["events"]["events_log_path"]))
        cfg["events"]["snapshot_dir"] = str(resolve_path(cfg["events"]["snapshot_dir"]))

    return cfg
