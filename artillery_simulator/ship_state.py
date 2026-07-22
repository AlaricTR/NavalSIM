"""Shared mutable ship combat state for one-way and mutual engagements."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple
import random

from .models import RepairModel, ShellType, ShipModel


@dataclass
class ShipCombatState:
    hp: float
    flooding: float = 0.0
    active_holes: int = 0
    max_active_holes: int = 0
    repair_finish_time: Optional[float] = None

    @classmethod
    def new(cls, ship: ShipModel) -> "ShipCombatState":
        return cls(hp=ship.max_hp)

    def schedule_repair(self, current_time: float, repair: RepairModel) -> None:
        if self.active_holes <= 0:
            self.repair_finish_time = None
            return
        self.repair_finish_time = current_time + repair.repair_time_for_holes(
            self.active_holes
        )

    def finish_repair(self, current_time: float, repair: RepairModel) -> None:
        if self.active_holes > 0:
            self.active_holes -= 1
        self.schedule_repair(current_time, repair)

    def advance_flooding(
        self,
        dt: float,
        ship: ShipModel,
        power_bucketers: int,
    ) -> None:
        net_holes = max(0, self.active_holes - power_bucketers)
        if net_holes <= 0 or dt <= 0:
            return
        whole_ship_fill_time_per_hole = (
            ship.seconds_per_hole_to_fill_one_compartment
            * ship.compartment_count
        )
        self.flooding += dt * net_holes / whole_ship_fill_time_per_hole

    def apply_probabilistic_shell(
        self,
        rng: random.Random,
        p_damage: float,
        p_hole: float,
        shell: ShellType,
        current_time: float,
        repair: RepairModel,
    ) -> Tuple[bool, bool]:
        damaging_hit = rng.random() < p_damage
        hole_created = rng.random() < p_hole

        if damaging_hit:
            self.hp -= shell.effective_damage
        if hole_created:
            self.active_holes += 1
            self.max_active_holes = max(self.max_active_holes, self.active_holes)
            if self.repair_finish_time is None:
                self.schedule_repair(current_time, repair)

        return damaging_hit, hole_created

    def death_outcome(self) -> Optional[str]:
        if self.flooding >= 1.0:
            self.flooding = 1.0
            return "flooding_death"
        if self.hp <= 0:
            self.hp = 0.0
            return "hp_death"
        return None
