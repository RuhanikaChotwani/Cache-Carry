"""Alert store service for IBVAP:
Stores verified alerts generated strictly from real AI match events.
Zero fake/timer-based alert generation.
"""

import json
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ALERTS_FILE = DATA_DIR / "alerts.json"

_alerts = []


def _load_alerts():
    global _alerts
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if ALERTS_FILE.exists():
        try:
            with open(ALERTS_FILE, "r") as f:
                _alerts = json.load(f)
        except Exception:
            _alerts = []
    else:
        _alerts = []
        _save_alerts()


def _save_alerts():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(ALERTS_FILE, "w") as f:
        json.dump(_alerts, f, indent=2)


_load_alerts()


def get_alerts(limit=100):
    return _alerts[:limit]


def add_alert(alert: dict):
    global _alerts
    _alerts.insert(0, alert)
    if len(_alerts) > 200:
        _alerts = _alerts[:200]
    _save_alerts()
    return alert


def clear_alerts():
    global _alerts
    _alerts = []
    _save_alerts()
    return {"status": "cleared"}
