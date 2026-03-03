"""Helpers for loading and updating system-wide configuration stored in the database.

This bridges environment-based defaults from ``app.config.config`` with the
``SystemConfig`` key/value table so that key hydraulic and zone parameters
become user-configurable at runtime via the database.
"""

from typing import Any, Dict, List, Tuple

from sqlalchemy.exc import IntegrityError

from app.models.system_config import SystemConfig
from app.config import config as default_config


# Schema describing which settings are persisted in SystemConfig and how.
# Keys are names used in API payloads; each entry maps to the underlying
# SystemConfig.key plus default value and description.
SYSTEM_CONFIG_SCHEMA: Dict[str, Dict[str, Any]] = {
    # Zone-level physical parameters (single-zone system)
    "zone_slope_degrees": {
        "db_key": "ZONE_SLOPE_DEGREES",
        "type": float,
        "default": getattr(default_config, "ZONE_SLOPE_DEGREES", 25.0),
        "description": "Zone slope angle in degrees",
    },
    "zone_area_m2": {
        "db_key": "ZONE_AREA_M2",
        "type": float,
        "default": getattr(default_config, "ZONE_AREA_M2", 1200.0),
        "description": "Zone area in square meters",
    },
    "zone_base_pressure_kpa": {
        "db_key": "ZONE_BASE_PRESSURE_KPA",
        "type": float,
        "default": getattr(default_config, "ZONE_BASE_PRESSURE_KPA", 200.0),
        "description": "Base emitter/sprinkler pressure requirement in kPa",
    },
    # Pipe / hydraulic geometry for main irrigation line
    "pipe_length_m": {
        "db_key": "PIPE_LENGTH_M",
        "type": float,
        "default": getattr(default_config, "PIPE_LENGTH_M", 50.0),
        "description": "Total main pipe run length in meters",
    },
    "pipe_diameter_m": {
        "db_key": "PIPE_DIAMETER_M",
        "type": float,
        "default": getattr(default_config, "PIPE_DIAMETER_M", 0.050),
        "description": "Internal main pipe diameter in meters",
    },
    "estimated_flow_rate_m3_per_s": {
        "db_key": "ESTIMATED_FLOW_RATE_M3_PER_S",
        "type": float,
        "default": getattr(default_config, "ESTIMATED_FLOW_RATE_M3_PER_S", 0.001),
        "description": "Estimated volumetric flow rate in m^3/s",
    },
}


def load_system_config(db) -> Dict[str, Any]:
    """Load system configuration values from the database.

    Missing keys are initialized using environment/default values from
    ``app.config.config`` so the system has sensible defaults even before
    the user customizes anything.
    """
    config_values: Dict[str, Any] = {}

    # First pass: determine which keys are missing and need seeding.
    to_seed: List[Tuple[str, Any, str]] = []
    for meta in SYSTEM_CONFIG_SCHEMA.values():
        db_key = meta["db_key"]
        default_value = meta.get("default")
        description = meta.get("description")

        row = db.query(SystemConfig).filter_by(key=db_key).first()
        if row is None:
            to_seed.append((db_key, default_value, description))

    # Batch-insert any missing keys and commit once. Handle races where another
    # process inserts the same key between our check and commit.
    if to_seed:
        try:
            for db_key, default_value, description in to_seed:
                db.add(SystemConfig(key=db_key, value=str(default_value), description=description))
            db.commit()
        except IntegrityError:
            # Another process may have inserted some/all keys; rollback and
            # re-read below without assuming our inserts succeeded.
            db.rollback()

    # Second pass: build the typed config dict from whatever is now in the DB,
    # falling back to defaults if conversion fails or a row is still absent.
    for name, meta in SYSTEM_CONFIG_SCHEMA.items():
        db_key = meta["db_key"]
        default_value = meta.get("default")
        value_type = meta.get("type", float)

        row = db.query(SystemConfig).filter_by(key=db_key).first()
        if row is None:
            # As a last resort, use the default directly without seeding again.
            config_values[name] = default_value
            continue

        try:
            typed_value = value_type(row.value)
        except (TypeError, ValueError):
            typed_value = default_value

        config_values[name] = typed_value

    return config_values


def update_system_config(db, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Apply partial updates to the system configuration.

    ``updates`` should use the public field names from SYSTEM_CONFIG_SCHEMA
    (e.g., ``zone_slope_degrees``, ``pipe_length_m``).

    Returns a structured result:
      - ``config``: full typed configuration after applying updates
      - ``applied_keys``: list of field names that were successfully updated
      - ``unknown_keys``: list of field names that are not in SYSTEM_CONFIG_SCHEMA
      - ``invalid_values``: mapping of field name -> raw value that failed validation/casting
    """
    result: Dict[str, Any] = {
        "config": None,
        "applied_keys": [],       # type: List[str]
        "unknown_keys": [],       # type: List[str]
        "invalid_values": {},     # type: Dict[str, Any]
    }

    if not updates:
        # Nothing to change; just return current config.
        result["config"] = load_system_config(db)
        return result

    applied_keys: List[str] = []
    unknown_keys: List[str] = []
    invalid_values: Dict[str, Any] = {}

    for name, raw_value in updates.items():
        meta = SYSTEM_CONFIG_SCHEMA.get(name)
        if not meta:
            # Track unknown keys so the API layer can report them to clients.
            unknown_keys.append(name)
            continue

        db_key = meta["db_key"]
        value_type = meta.get("type", float)
        description = meta.get("description")

        # Best-effort cast; if cast fails we keep the previous value and report the error.
        try:
            cast_value = value_type(raw_value)
        except (TypeError, ValueError):
            invalid_values[name] = raw_value
            continue

        row = db.query(SystemConfig).filter_by(key=db_key).first()
        if row is None:
            row = SystemConfig(key=db_key, value=str(cast_value), description=description)
            db.add(row)
        else:
            row.value = str(cast_value)

        applied_keys.append(name)

    db.commit()

    result["config"] = load_system_config(db)
    result["applied_keys"] = applied_keys
    result["unknown_keys"] = unknown_keys
    result["invalid_values"] = invalid_values
    return result

