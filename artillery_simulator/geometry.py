"""Geometry and hit-probability calculations."""
from __future__ import annotations

import math
from typing import Tuple

from .models import GunModel, ShellType, ShipModel


def rectangle_dimensions_from_area(
    area_m2: float, ratio_l_to_w: float
) -> Tuple[float, float]:
    width = math.sqrt(area_m2 / ratio_l_to_w)
    length = ratio_l_to_w * width
    return length, width


def expanded_rectangle_area(
    length: float, width: float, radius: float
) -> float:
    perimeter = 2.0 * (length + width)
    return (
        length * width
        + perimeter * radius
        + math.pi * radius * radius
    )


def compute_hit_probabilities(
    ship: ShipModel, shell: ShellType, gun: GunModel
) -> Tuple[float, float]:
    length, width = rectangle_dimensions_from_area(
        ship.area_m2, ship.length_width_ratio
    )

    dispersion_area = math.pi * gun.spread_radius_m**2
    damage_area = expanded_rectangle_area(
        length, width, shell.damage_radius_m
    )
    valid_hole_area = max(0.0, damage_area - ship.area_m2)

    p_damage = min(1.0, damage_area / dispersion_area)
    p_hole = (
        min(1.0, valid_hole_area / dispersion_area)
        * shell.hole_chance_on_valid_hit
    )
    return p_damage, p_hole
