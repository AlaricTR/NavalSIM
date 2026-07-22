"""Load and validate artillery, shell, and ship definitions from JSON."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Tuple

from .models import ArtilleryPlatform, ShellType, ShipDefinition

DATA_FILENAME = "artillery_data_v6.json"


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
        f"Could not find {DATA_FILENAME}. Place it beside the launcher."
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

        deployment_type = str(item.get("deployment_type", "")).lower()
        entrenchment_radius = item.get("entrenchment_radius_m")
        physical_width = item.get("physical_width_m")

        platform = ArtilleryPlatform(
            name=str(item.get("name", key)),
            min_range_m=require_number(item, "min_range_m", key),
            max_range_m=require_number(item, "max_range_m", key),
            min_spread_m=require_number(item, "min_spread_m", key),
            max_spread_m=require_number(item, "max_spread_m", key),
            firing_time_s=require_number(item, "firing_time_s", key),
            reload_time_s=require_number(item, "reload_time_s", key),
            shell_type=str(shell_type),
            max_hp=require_number(item, "max_hp", key),
            damage_resistance=require_number(item, "damage_resistance", key),
            deployment_type=deployment_type,
            center_spacing_m=require_number(item, "center_spacing_m", key),
            entrenchment_radius_m=(
                float(entrenchment_radius)
                if isinstance(entrenchment_radius, (int, float))
                else None
            ),
            physical_width_m=(
                float(physical_width)
                if isinstance(physical_width, (int, float))
                else None
            ),
        )

        if platform.max_range_m < platform.min_range_m:
            raise ValueError(f"{key} has max range below min range.")
        if platform.max_spread_m <= 0 or platform.min_spread_m <= 0:
            raise ValueError(f"{key} spread values must be positive.")
        if platform.cycle_time_s <= 0:
            raise ValueError(f"{key} firing cycle must be positive.")
        if platform.max_hp <= 0:
            raise ValueError(f"{key} max_hp must be positive.")
        if not 0.0 <= platform.damage_resistance < 1.0:
            raise ValueError(f"{key} damage_resistance must be 0 to less than 1.")
        if platform.center_spacing_m <= 0:
            raise ValueError(f"{key} center_spacing_m must be positive.")
        if deployment_type not in {"entrenched", "pushgun"}:
            raise ValueError(
                f"{key} deployment_type must be 'entrenched' or 'pushgun'."
            )
        if deployment_type == "entrenched":
            if platform.entrenchment_radius_m is None or platform.entrenchment_radius_m <= 0:
                raise ValueError(
                    f"{key} must define a positive entrenchment_radius_m."
                )
        if deployment_type == "pushgun":
            if platform.physical_width_m is None or platform.physical_width_m <= 0:
                raise ValueError(f"{key} must define a positive physical_width_m.")

        platforms[key] = platform

    ships: Dict[str, ShipDefinition] = {}
    for key, item in ships_raw.items():
        if not isinstance(item, dict):
            raise ValueError(f"ships.{key} must be an object.")

        turret_shell_type = str(item.get("turret_shell_type", ""))
        if turret_shell_type not in shells:
            raise ValueError(
                f"{key} references undefined turret shell {turret_shell_type!r}."
            )

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
            turret_shell_type=turret_shell_type,
        )

        if ship.max_hp <= 0 or ship.area_m2 <= 0:
            raise ValueError(f"{key} HP and area must be positive.")
        if ship.compartment_count <= 0:
            raise ValueError(f"{key} must have at least one compartment.")
        if ship.seconds_per_hole_to_fill_one_compartment <= 0:
            raise ValueError(f"{key} flooding time must be positive.")
        if ship.turret_count <= 0 or ship.shells_per_turret <= 0:
            raise ValueError(f"{key} turret values must be positive.")
        if ship.reload_time_per_turret_s <= 0:
            raise ValueError(f"{key} turret reload time must be positive.")

        ships[key] = ship

    return platforms, ships, shells, ship_resistance


def build_shell_type(
    shell_key: str,
    shell_data: Dict[str, dict],
    target_resistance: float,
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
    if not 0.0 <= target_resistance < 1.0:
        raise ValueError("target_resistance must be between 0 and 1.")

    return ShellType(
        name=str(raw.get("name", shell_key)),
        base_damage=base_damage,
        effective_damage=base_damage * (1.0 - target_resistance),
        damage_radius_m=radius,
        hole_chance_on_valid_hit=hole_chance,
    )
