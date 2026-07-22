"""Core immutable data models used by the simulator."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ShellType:
    name: str
    base_damage: float
    effective_damage: float
    damage_radius_m: float
    hole_chance_on_valid_hit: float = 0.50


@dataclass(frozen=True)
class ArtilleryPlatform:
    name: str
    min_range_m: float
    max_range_m: float
    min_spread_m: float
    max_spread_m: float
    firing_time_s: float
    reload_time_s: float
    shell_type: str

    @property
    def cycle_time_s(self) -> float:
        return self.firing_time_s + self.reload_time_s

    def spread_at_range(self, engagement_range_m: float) -> float:
        if not self.min_range_m <= engagement_range_m <= self.max_range_m:
            raise ValueError(
                f"{self.name} supports ranges from {self.min_range_m:g}m "
                f"to {self.max_range_m:g}m."
            )

        range_span = self.max_range_m - self.min_range_m
        if range_span <= 0:
            return self.min_spread_m

        fraction = (engagement_range_m - self.min_range_m) / range_span
        return self.min_spread_m + fraction * (
            self.max_spread_m - self.min_spread_m
        )


@dataclass(frozen=True)
class GunModel:
    name: str
    spread_radius_m: float
    cycle_time_s: float


@dataclass(frozen=True)
class BatteryModel:
    platform: ArtilleryPlatform
    gun: GunModel
    shell: ShellType
    gun_count: int
    engagement_range_m: float


@dataclass(frozen=True)
class ShipDefinition:
    name: str
    max_hp: float
    area_m2: float
    compartment_count: int
    seconds_per_hole_to_fill_one_compartment: float
    turret_count: int
    reload_time_per_turret_s: float
    shells_per_turret: int


@dataclass(frozen=True)
class ShipModel:
    name: str
    max_hp: float
    area_m2: float
    length_width_ratio: float = 60.0 / 11.0
    seconds_per_hole_to_fill_one_compartment: float = 440.0
    compartment_count: int = 4


@dataclass(frozen=True)
class RepairModel:
    min_repair_time_s: float
    max_repair_time_s: float
    holes_for_max_time: int = 10

    def repair_time_for_holes(self, active_holes: int) -> float:
        if active_holes <= 1:
            return self.min_repair_time_s
        if active_holes >= self.holes_for_max_time:
            return self.max_repair_time_s

        span = self.holes_for_max_time - 1
        fraction = (active_holes - 1) / span
        return self.min_repair_time_s + fraction * (
            self.max_repair_time_s - self.min_repair_time_s
        )


@dataclass(frozen=True)
class RetreatRule:
    leak_threshold_low: int
    leak_threshold_high: int
    hp_retreat_fraction: float
    shells_per_gun_after_retreat: int


@dataclass(frozen=True)
class SimulationConfig:
    battery: BatteryModel
    ship: ShipModel
    repair: RepairModel
    retreat: RetreatRule
    power_bucketers: int
    batch_size_per_threshold: int
    random_seed: Optional[int] = None
    max_time_s: float = 7200.0


@dataclass
class TrialResult:
    retreat_threshold: int
    survived: bool
    outcome: str
    time_s: float
    hp_left: float
    active_holes_end: int
    flooding_fraction_end: float
    max_active_holes: int
    retreat_triggered: bool
    retreat_reason: str
    total_shells_fired: int
    damaging_hits: int
    holes_created: int


@dataclass
class SummaryResult:
    retreat_threshold: int
    simulations: int
    survival_pct: float
    flooding_death_pct: float
    hp_death_pct: float
    avg_time_s: float
    median_time_s: float
    avg_hp_left: float
    avg_active_holes_end: float
    avg_flooding_pct_end: float
    avg_max_holes: float
    avg_shells_fired: float
    avg_damaging_hits: float
    avg_holes_created: float
