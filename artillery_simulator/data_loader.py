"""Load and validate artillery, shell, and ship definitions from JSON."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Tuple

from .models import ArtilleryPlatform, ShellType, ShipDefinition

DATA_FILENAME = "artillery_data_v5.json"


def resolve_data_path() -> Path:
    package_dir = Path(__file__).resolve().parent
    candidates = [
        package_dir.parent / DATA_FILENAME,
        package_dir / DATA_FILENAME,
        Path.cwd() / DATA_FILENAME,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"Could not find {DATA_FILENAME}. Place it beside this Python file."
    )


def require_number(mapping: dict, key: str, context: str) -> float:
    value = mapping.get(key)
    if not isinstance(value, (int, float)):
        raise ValueError(f"{context}.{key} must be a number.")
    return float(value)


def load_artillery_data(
    path: Path,
) -> Tuple[
    Dict[str, ArtilleryPlatform],
    Dict[str, ShipDefinition],
    Dict[str, dict],
    float,
]:
    with path.open("r", encoding="utf-8") as file:
        raw = json.load(file)

    shells = raw.get("shells")
    platforms_raw = raw.get("artillery_platforms")
    ships_raw = raw.get("ships")
    modifiers = raw.get("global_modifiers", {})

    if not isinstance(shells, dict) or not shells:
        raise ValueError("JSON must contain a non-empty 'shells' object.")
    if not isinstance(platforms_raw, dict) or not platforms_raw:
        raise ValueError(
            "JSON must contain a non-empty 'artillery_platforms' object."
        )
    if not isinstance(ships_raw, dict) or not ships_raw:
        raise ValueError("JSON must contain a non-empty 'ships' object.")

    ship_resistance = require_number(
        modifiers, "ship_damage_resistance", "global_modifiers"
    )
    if not 0.0 <= ship_resistance < 1.0:
        raise ValueError("ship_damage_resistance must be between 0 and 1.")

    platforms: Dict[str, ArtilleryPlatform] = {}
    for key, item in platforms_raw.items():
        if not isinstance(item, dict):
            raise ValueError(f"artillery_platforms.{key} must be an object.")

        shell_type = item.get("shell_type")
        if shell_type not in shells:
            raise ValueError(
                f"{key} references undefined shell type {shell_type!r}."
            )

        platform = ArtilleryPlatform(
            name=str(item.get("name", key)),
            min_range_m=require_number(item, "min_range_m", key),
            max_range_m=require_number(item, "max_range_m", key),
            min_spread_m=require_number(item, "min_spread_m", key),
            max_spread_m=require_number(item, "max_spread_m", key),
            firing_time_s=require_number(item, "firing_time_s", key),
            reload_time_s=require_number(item, "reload_time_s", key),
            shell_type=str(shell_type),
        )

        if platform.max_range_m < platform.min_range_m:
            raise ValueError(f"{key} has max range below min range.")
        if platform.max_spread_m < 0 or platform.min_spread_m <= 0:
            raise ValueError(f"{key} spread values must be positive.")
        if platform.cycle_time_s <= 0:
            raise ValueError(f"{key} firing cycle must be positive.")

        platforms[key] = platform

    ships: Dict[str, ShipDefinition] = {}
    for key, item in ships_raw.items():
        if not isinstance(item, dict):
            raise ValueError(f"ships.{key} must be an object.")

        ship = ShipDefinition(
            name=str(item.get("name", key)),
            max_hp=require_number(item, "max_hp", key),
            area_m2=require_number(item, "area_m2", key),
            compartment_count=int(require_number(item, "compartment_count", key)),
            seconds_per_hole_to_fill_one_compartment=require_number(
                item, "seconds_per_hole_to_fill_one_compartment", key
            ),
            turret_count=int(require_number(item, "turret_count", key)),
            reload_time_per_turret_s=require_number(
                item, "reload_time_per_turret_s", key
            ),
            shells_per_turret=int(require_number(item, "shells_per_turret", key)),
        )

        if ship.max_hp <= 0 or ship.area_m2 <= 0:
            raise ValueError(f"{key} HP and area must be positive.")
        if ship.compartment_count <= 0:
            raise ValueError(f"{key} must have at least one compartment.")
        if ship.seconds_per_hole_to_fill_one_compartment <= 0:
            raise ValueError(f"{key} flooding time must be positive.")
        if ship.turret_count < 0 or ship.shells_per_turret < 0:
            raise ValueError(f"{key} turret values cannot be negative.")
        if ship.reload_time_per_turret_s <= 0:
            raise ValueError(f"{key} turret reload time must be positive.")

        ships[key] = ship

    return platforms, ships, shells, ship_resistance


def build_shell_type(
    shell_key: str,
    shell_data: Dict[str, dict],
    ship_resistance: float,
) -> ShellType:
    raw = shell_data[shell_key]
    base_damage = require_number(raw, "base_damage", shell_key)
    radius = require_number(raw, "max_damage_radius_m", shell_key)
    hole_chance = require_number(
        raw, "hole_chance_on_valid_hit", shell_key
    )

    if base_damage < 0 or radius <= 0:
        raise ValueError(f"{shell_key} damage/radius values are invalid.")
    if not 0.0 <= hole_chance <= 1.0:
        raise ValueError(f"{shell_key} hole chance must be between 0 and 1.")

    return ShellType(
        name=str(raw.get("name", shell_key)),
        base_damage=base_damage,
        effective_damage=base_damage * (1.0 - ship_resistance),
        damage_radius_m=radius,
        hole_chance_on_valid_hit=hole_chance,
    )
