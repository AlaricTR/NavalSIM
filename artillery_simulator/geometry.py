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


def shell_damage_multiplier(distance_m: float, shell: ShellType) -> float:
    """Return 1 inside the full-damage radius, then linearly fall to 0."""
    if distance_m <= shell.damage_radius_m:
        return 1.0
    if distance_m >= shell.falloff_radius_m:
        return 0.0
    return (
        shell.falloff_radius_m - distance_m
    ) / (
        shell.falloff_radius_m - shell.damage_radius_m
    )


def point_to_centered_rectangle_distance(
    x: float,
    y: float,
    length: float,
    width: float,
) -> Tuple[float, bool]:
    """Shortest distance to a centered rectangle and whether point is on its deck."""
    half_length = length / 2.0
    half_width = width / 2.0
    on_deck = abs(x) <= half_length and abs(y) <= half_width
    dx = max(abs(x) - half_length, 0.0)
    dy = max(abs(y) - half_width, 0.0)
    return math.hypot(dx, dy), on_deck


def random_ship_impact(
    rng: random.Random,
    ship: ShipModel,
    shell: ShellType,
    gun: GunModel,
) -> Tuple[float, bool, bool]:
    """
    Sample one shell impact in the gun's spread circle.

    Returns (damage_multiplier, damaging_hit, leak_eligible). Deck impacts can
    damage but cannot create wet holes. Splash outside the deck can create a
    wet hole anywhere damage remains above zero, including the falloff band.
    """
    impact_x, impact_y = random_point_in_spread(rng, 0.0, gun.spread_radius_m)
    length, width = rectangle_dimensions_from_area(
        ship.area_m2, ship.length_width_ratio
    )
    distance, on_deck = point_to_centered_rectangle_distance(
        impact_x, impact_y, length, width
    )
    multiplier = shell_damage_multiplier(distance, shell)
    damaging_hit = multiplier > 0.0
    leak_eligible = damaging_hit and not on_deck
    return multiplier, damaging_hit, leak_eligible


def compute_hit_probabilities(
    ship: ShipModel, shell: ShellType, gun: GunModel
) -> Tuple[float, float]:
    length, width = rectangle_dimensions_from_area(
        ship.area_m2, ship.length_width_ratio
    )
    dispersion_area = math.pi * gun.spread_radius_m**2
    damage_area = expanded_rectangle_area(length, width, shell.falloff_radius_m)
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
) -> List[Tuple[int, float]]:
    """
    Return (gun_index, damage_multiplier) for every damaged gun.

    Entrenchments are a hard gate: an impact outside the trench does no damage
    even if shell splash would otherwise reach the gun. Pushguns receive normal
    full/falloff splash damage out to the shell's outer radius.
    """
    impacted: List[Tuple[int, float]] = []
    for index in living_indices:
        distance = math.hypot(impact_x - centers[index], impact_y)

        if platform.deployment_type == "entrenched":
            trench_radius = platform.entrenchment_radius_m or 0.0
            if distance > trench_radius + 1e-9:
                continue

        multiplier = shell_damage_multiplier(distance, shell)
        if multiplier > 0.0:
            impacted.append((index, multiplier))
    return impacted
