"""Mutual ship-versus-battery duel simulation."""
from __future__ import annotations

import math
import random
import statistics
from typing import List, Optional, Sequence, Tuple

from .geometry import (
    RETARGET_MAX_S,
    RETARGET_MIN_S,
    choose_best_aim_center,
    compute_hit_probabilities,
    impacted_guns,
    linear_gun_centers,
    naval_spread_at_range,
    needs_retarget,
    random_point_in_spread,
)
from .models import (
    DuelSummaryResult,
    DuelTrialResult,
    ShellType,
    SimulationConfig,
    SummaryResult,
    TrialResult,
)
from .ship_state import ShipCombatState
from .simulation import summarize_trials


class DuelEngagementSimulator:
    """Simulate both sides firing until retreat, destruction, or timeout."""

    def __init__(self, config: SimulationConfig, naval_shell: ShellType):
        if not config.duel_enabled:
            raise ValueError("Duel simulator requires duel_enabled=True.")
        self.config = config
        self.naval_shell = naval_shell
        self.rng = random.Random(config.random_seed)
        self.p_damage, self.p_hole = compute_hit_probabilities(
            config.ship, config.battery.shell, config.battery.gun
        )
        self.naval_spread_m = naval_spread_at_range(
            config.battery.engagement_range_m
        )
        self.gun_centers = linear_gun_centers(
            config.battery.gun_count,
            config.battery.platform.center_spacing_m,
        )

    def _living_indices(self, gun_hp: Sequence[float]) -> List[int]:
        return [index for index, hp in enumerate(gun_hp) if hp > 0.0]

    def _fire_ship_volley(
        self,
        gun_hp: List[float],
        aim_x: float,
    ) -> Tuple[int, int]:
        cfg = self.config
        shell_count = cfg.ship.turret_count * cfg.ship.shells_per_turret
        impact_count = 0
        effective_damage = self.naval_shell.base_damage * (
            1.0 - cfg.battery.platform.damage_resistance
        )

        for _ in range(shell_count):
            impact_x, impact_y = random_point_in_spread(
                self.rng, aim_x, self.naval_spread_m
            )
            living = self._living_indices(gun_hp)
            targets = impacted_guns(
                impact_x,
                impact_y,
                self.gun_centers,
                living,
                cfg.battery.platform,
                self.naval_shell,
            )
            impact_count += len(targets)
            for index in targets:
                gun_hp[index] = max(0.0, gun_hp[index] - effective_damage)

        return shell_count, impact_count

    def run_trial(self, retreat_threshold: int) -> DuelTrialResult:
        cfg = self.config
        state = ShipCombatState.new(cfg.ship)
        gun_hp = [cfg.battery.platform.max_hp] * cfg.battery.gun_count
        next_battery_shot = [0.0] * cfg.battery.gun_count
        post_retreat_remaining = [
            cfg.retreat.shells_per_gun_after_retreat
            for _ in range(cfg.battery.gun_count)
        ]
        next_ship_volley = 0.0
        current_aim_x: Optional[float] = None

        time_s = 0.0
        retreat_triggered = False
        retreat_reason = ""
        battery_outcome: Optional[str] = None
        battery_outcome_time: Optional[float] = None
        battery_destroyed_time: Optional[float] = None

        battery_shells_fired = 0
        battery_damaging_hits = 0
        holes_created = 0
        ship_shells_fired = 0
        ship_shell_impacts = 0
        retarget_count = 0
        final_outcome = "timeout"
        survived = False

        while time_s < cfg.max_time_s:
            next_battery_event = min(next_battery_shot, default=math.inf)
            next_repair_event = (
                state.repair_finish_time
                if state.repair_finish_time is not None
                else math.inf
            )
            next_event = min(
                next_battery_event,
                next_ship_volley,
                next_repair_event,
            )

            if next_event == math.inf:
                survived = state.death_outcome() is None
                if retreat_triggered:
                    final_outcome = "survived_retreat" if survived else final_outcome
                else:
                    final_outcome = "survived" if survived else final_outcome
                break

            dt = next_event - time_s
            if dt < -1e-9:
                raise RuntimeError("Negative time step detected in duel.")
            state.advance_flooding(dt, cfg.ship, cfg.power_bucketers)
            time_s = next_event

            death_before_fire = state.death_outcome()
            if death_before_fire:
                final_outcome = death_before_fire
                if battery_outcome is None:
                    battery_outcome = "ship_destroyed"
                    battery_outcome_time = time_s
                break

            if (
                state.repair_finish_time is not None
                and abs(time_s - state.repair_finish_time) < 1e-9
            ):
                state.finish_repair(time_s, cfg.repair)

            living_at_event_start = self._living_indices(gun_hp)
            battery_shooters = [
                index
                for index in living_at_event_start
                if abs(next_battery_shot[index] - time_s) < 1e-9
            ]
            ship_volley_due = (
                abs(next_ship_volley - time_s) < 1e-9
                and not retreat_triggered
                and bool(living_at_event_start)
                and state.death_outcome() is None
            )

            # Determine aim or spend this event retargeting. The first aim is free.
            ship_fires_now = False
            aim_for_volley: Optional[float] = None
            if ship_volley_due:
                must_retarget, desired_aim, _ = needs_retarget(
                    current_aim_x,
                    self.gun_centers,
                    living_at_event_start,
                    self.naval_spread_m,
                )
                if current_aim_x is None:
                    current_aim_x = desired_aim
                    ship_fires_now = True
                    aim_for_volley = current_aim_x
                elif must_retarget:
                    current_aim_x = desired_aim
                    retarget_count += 1
                    next_ship_volley = time_s + self.rng.uniform(
                        RETARGET_MIN_S, RETARGET_MAX_S
                    )
                else:
                    ship_fires_now = True
                    aim_for_volley = current_aim_x

            # Battery shots and the ship volley scheduled for the same instant are
            # treated as simultaneous. Destruction is applied after both attacks.
            for index in battery_shooters:
                if retreat_triggered:
                    if post_retreat_remaining[index] <= 0:
                        next_battery_shot[index] = math.inf
                        continue
                    post_retreat_remaining[index] -= 1

                battery_shells_fired += 1
                hit, hole = state.apply_probabilistic_shell(
                    self.rng,
                    self.p_damage,
                    self.p_hole,
                    cfg.battery.shell,
                    time_s,
                    cfg.repair,
                )
                battery_damaging_hits += int(hit)
                holes_created += int(hole)

                if retreat_triggered and post_retreat_remaining[index] <= 0:
                    next_battery_shot[index] = math.inf
                else:
                    next_battery_shot[index] = (
                        time_s + cfg.battery.gun.cycle_time_s
                    )

            if ship_fires_now and aim_for_volley is not None:
                shells, impacts = self._fire_ship_volley(gun_hp, aim_for_volley)
                ship_shells_fired += shells
                ship_shell_impacts += impacts
                next_ship_volley = time_s + cfg.ship.reload_time_per_turret_s

            # Any gun destroyed by this simultaneous event cannot fire later.
            for index, hp in enumerate(gun_hp):
                if hp <= 0.0:
                    next_battery_shot[index] = math.inf
                    post_retreat_remaining[index] = 0

            death_after_fire = state.death_outcome()
            living_after = self._living_indices(gun_hp)
            battery_dead_now = not living_after

            newly_retreating = False
            if not retreat_triggered and death_after_fire is None:
                hp_fraction = state.hp / cfg.ship.max_hp
                if hp_fraction <= cfg.retreat.hp_retreat_fraction:
                    retreat_triggered = True
                    retreat_reason = "hp"
                    newly_retreating = True
                elif state.active_holes >= retreat_threshold:
                    retreat_triggered = True
                    retreat_reason = "holes"
                    newly_retreating = True

            if battery_outcome is None:
                if battery_dead_now and (newly_retreating or death_after_fire):
                    battery_outcome = "simultaneous"
                    battery_outcome_time = time_s
                    battery_destroyed_time = time_s
                elif battery_dead_now:
                    battery_outcome = "battery_destroyed_first"
                    battery_outcome_time = time_s
                    battery_destroyed_time = time_s
                elif newly_retreating:
                    battery_outcome = "forced_retreat"
                    battery_outcome_time = time_s
                elif death_after_fire:
                    battery_outcome = "ship_destroyed"
                    battery_outcome_time = time_s

            if death_after_fire:
                final_outcome = death_after_fire
                break

            if newly_retreating:
                # The ship stops engaging the battery while retreating. Every gun
                # still alive receives the configured number of follow-up shots.
                next_ship_volley = math.inf
                for index in range(cfg.battery.gun_count):
                    if gun_hp[index] <= 0.0:
                        post_retreat_remaining[index] = 0
                if all(value <= 0 for value in post_retreat_remaining):
                    next_battery_shot = [math.inf] * cfg.battery.gun_count

            if battery_dead_now and not retreat_triggered:
                next_ship_volley = math.inf
                next_battery_shot = [math.inf] * cfg.battery.gun_count

            if retreat_triggered:
                for index in range(cfg.battery.gun_count):
                    if (
                        gun_hp[index] > 0.0
                        and post_retreat_remaining[index] <= 0
                    ):
                        next_battery_shot[index] = math.inf

            no_more_fire = (
                next_ship_volley == math.inf
                and all(value == math.inf for value in next_battery_shot)
            )
            if no_more_fire and state.active_holes <= 0:
                survived = state.death_outcome() is None
                final_outcome = (
                    "survived_retreat"
                    if retreat_triggered and survived
                    else "survived"
                    if survived
                    else final_outcome
                )
                break

        if time_s >= cfg.max_time_s and final_outcome == "timeout":
            survived = state.death_outcome() is None
            final_outcome = "timeout_alive" if survived else "timeout_dead"
            if battery_outcome is None:
                battery_outcome = "timeout"
                battery_outcome_time = time_s

        if battery_outcome is None:
            battery_outcome = "timeout"
        if battery_outcome_time is None:
            battery_outcome_time = time_s

        ship_result = TrialResult(
            retreat_threshold=retreat_threshold,
            survived=survived,
            outcome=final_outcome,
            time_s=time_s,
            hp_left=max(0.0, state.hp),
            active_holes_end=state.active_holes,
            flooding_fraction_end=min(1.0, state.flooding),
            max_active_holes=state.max_active_holes,
            retreat_triggered=retreat_triggered,
            retreat_reason=retreat_reason,
            total_shells_fired=battery_shells_fired,
            damaging_hits=battery_damaging_hits,
            holes_created=holes_created,
        )

        guns_remaining = len(self._living_indices(gun_hp))
        return DuelTrialResult(
            ship_result=ship_result,
            battery_outcome=battery_outcome,
            battery_outcome_time_s=battery_outcome_time,
            battery_destroyed_time_s=battery_destroyed_time,
            guns_destroyed=cfg.battery.gun_count - guns_remaining,
            guns_remaining=guns_remaining,
            battery_hp_left=sum(max(0.0, hp) for hp in gun_hp),
            ship_shells_fired=ship_shells_fired,
            ship_shell_impacts=ship_shell_impacts,
            retarget_count=retarget_count,
        )

    def run_batches(
        self,
    ) -> Tuple[
        List[SummaryResult],
        List[DuelSummaryResult],
        List[DuelTrialResult],
    ]:
        ship_summaries: List[SummaryResult] = []
        duel_summaries: List[DuelSummaryResult] = []
        all_trials: List[DuelTrialResult] = []

        for threshold in range(
            self.config.retreat.leak_threshold_low,
            self.config.retreat.leak_threshold_high + 1,
        ):
            trials = [
                self.run_trial(threshold)
                for _ in range(self.config.batch_size_per_threshold)
            ]
            all_trials.extend(trials)
            ship_summaries.append(
                summarize_trials(
                    threshold, [trial.ship_result for trial in trials]
                )
            )
            duel_summaries.append(summarize_duel_trials(threshold, trials))

        return ship_summaries, duel_summaries, all_trials


def summarize_duel_trials(
    threshold: int,
    trials: List[DuelTrialResult],
) -> DuelSummaryResult:
    if not trials:
        raise ValueError("Cannot summarize zero duel trials.")
    n = len(trials)

    def pct(outcome: str) -> float:
        return 100.0 * sum(
            1 for trial in trials if trial.battery_outcome == outcome
        ) / n

    destruction_times = [
        trial.battery_destroyed_time_s
        for trial in trials
        if trial.battery_destroyed_time_s is not None
    ]

    return DuelSummaryResult(
        retreat_threshold=threshold,
        simulations=n,
        forced_retreat_pct=pct("forced_retreat"),
        battery_dead_first_pct=pct("battery_destroyed_first"),
        ship_destroyed_pct=pct("ship_destroyed"),
        simultaneous_pct=pct("simultaneous"),
        timeout_pct=pct("timeout"),
        avg_battery_time_in_fight_s=statistics.mean(
            trial.battery_outcome_time_s for trial in trials
        ),
        median_battery_time_in_fight_s=statistics.median(
            trial.battery_outcome_time_s for trial in trials
        ),
        avg_battery_death_time_s=(
            statistics.mean(destruction_times) if destruction_times else None
        ),
        avg_guns_destroyed=statistics.mean(
            trial.guns_destroyed for trial in trials
        ),
        avg_guns_remaining=statistics.mean(
            trial.guns_remaining for trial in trials
        ),
        avg_battery_hp_left=statistics.mean(
            trial.battery_hp_left for trial in trials
        ),
        avg_ship_shells_fired=statistics.mean(
            trial.ship_shells_fired for trial in trials
        ),
        avg_ship_shell_impacts=statistics.mean(
            trial.ship_shell_impacts for trial in trials
        ),
        avg_retargets=statistics.mean(trial.retarget_count for trial in trials),
    )
