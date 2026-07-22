"""Geometry, spread interpolation, and line-battery targeting helpers."""
from __future__ import annotations

import math
import random
from typing import Iterable, List, Optional, Sequence, Tuple

from .models import ArtilleryPlatform, GunModel, ShellType, ShipModel

NAVAL_MIN_RANGE_M = 100.0
NAVAL_MAX_RANGE_M = 200.0
NAVAL_MIN_SPREAD_M = 2.5
NAVAL_MAX_SPREAD_M = 8.5
RETARGET_MIN_S = 5.0
RETARGET_MAX_S = 10.0


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
    return length * width + perimeter * radius + math.pi * radius * radius


def compute_hit_probabilities(
    ship: ShipModel, shell: ShellType, gun: GunModel
) -> Tuple[float, float]:
    length, width = rectangle_dimensions_from_area(
        ship.area_m2, ship.length_width_ratio
    )
    dispersion_area = math.pi * gun.spread_radius_m**2
    damage_area = expanded_rectangle_area(length, width, shell.damage_radius_m)
    valid_hole_area = max(0.0, damage_area - ship.area_m2)

    p_damage = min(1.0, damage_area / dispersion_area)
    p_hole = (
        min(1.0, valid_hole_area / dispersion_area)
        * shell.hole_chance_on_valid_hit
    )
    return p_damage, p_hole


def naval_spread_at_range(engagement_range_m: float) -> float:
    """Hardcoded naval spread curve, clamped outside 100-200 metres."""
    if engagement_range_m <= NAVAL_MIN_RANGE_M:
        return NAVAL_MIN_SPREAD_M
    if engagement_range_m >= NAVAL_MAX_RANGE_M:
        return NAVAL_MAX_SPREAD_M

    fraction = (
        (engagement_range_m - NAVAL_MIN_RANGE_M)
        / (NAVAL_MAX_RANGE_M - NAVAL_MIN_RANGE_M)
    )
    return NAVAL_MIN_SPREAD_M + fraction * (
        NAVAL_MAX_SPREAD_M - NAVAL_MIN_SPREAD_M
    )


def linear_gun_centers(gun_count: int, center_spacing_m: float) -> List[float]:
    if gun_count <= 0:
        return []
    midpoint = (gun_count - 1) / 2.0
    return [(index - midpoint) * center_spacing_m for index in range(gun_count)]


def covered_living_guns(
    aim_x: float,
    spread_radius_m: float,
    centers: Sequence[float],
    living_indices: Iterable[int],
) -> List[int]:
    return [
        index
        for index in living_indices
        if abs(centers[index] - aim_x) <= spread_radius_m + 1e-9
    ]


def choose_best_aim_center(
    centers: Sequence[float],
    living_indices: Sequence[int],
    spread_radius_m: float,
    previous_aim_x: Optional[float] = None,
) -> Tuple[float, List[int]]:
    """Choose a point covering the largest contiguous set of living guns."""
    if not living_indices:
        raise ValueError("Cannot aim at an empty battery.")

    ordered = sorted(living_indices, key=lambda index: centers[index])
    best_covered: List[int] = []
    best_aim = centers[ordered[0]]
    best_tie_distance = math.inf

    for start_pos, start_index in enumerate(ordered):
        for end_pos in range(start_pos, len(ordered)):
            end_index = ordered[end_pos]
            if centers[end_index] - centers[start_index] > 2.0 * spread_radius_m + 1e-9:
                break
            covered = ordered[start_pos : end_pos + 1]
            aim = (centers[start_index] + centers[end_index]) / 2.0
            tie_anchor = previous_aim_x if previous_aim_x is not None else 0.0
            tie_distance = abs(aim - tie_anchor)
            if (
                len(covered) > len(best_covered)
                or (
                    len(covered) == len(best_covered)
                    and tie_distance < best_tie_distance - 1e-9
                )
            ):
                best_covered = list(covered)
                best_aim = aim
                best_tie_distance = tie_distance

    return best_aim, best_covered


def needs_retarget(
    current_aim_x: Optional[float],
    centers: Sequence[float],
    living_indices: Sequence[int],
    spread_radius_m: float,
) -> Tuple[bool, float, List[int]]:
    desired_aim, desired_covered = choose_best_aim_center(
        centers, living_indices, spread_radius_m, current_aim_x
    )
    if current_aim_x is None:
        return False, desired_aim, desired_covered

    current_covered = covered_living_guns(
        current_aim_x, spread_radius_m, centers, living_indices
    )
    must_retarget = len(desired_covered) > len(current_covered)
    return must_retarget, desired_aim, desired_covered


def random_point_in_spread(
    rng: random.Random,
    aim_x: float,
    spread_radius_m: float,
) -> Tuple[float, float]:
    radius = spread_radius_m * math.sqrt(rng.random())
    angle = 2.0 * math.pi * rng.random()
    return aim_x + radius * math.cos(angle), radius * math.sin(angle)


def impacted_guns(
    impact_x: float,
    impact_y: float,
    centers: Sequence[float],
    living_indices: Iterable[int],
    platform: ArtilleryPlatform,
    shell: ShellType,
) -> List[int]:
    if platform.deployment_type == "entrenched":
        vulnerable_radius = platform.entrenchment_radius_m or 0.0
    else:
        vulnerable_radius = shell.damage_radius_m

    impacted: List[int] = []
    for index in living_indices:
        distance = math.hypot(impact_x - centers[index], impact_y)
        if distance <= vulnerable_radius + 1e-9:
            impacted.append(index)
    return impacted
