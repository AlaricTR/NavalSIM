"""Monte Carlo engagement engine and trial summarization."""
from __future__ import annotations

import math
import random
import statistics
from typing import List, Optional, Tuple

from .geometry import compute_hit_probabilities
from .models import SimulationConfig, SummaryResult, TrialResult


class EngagementSimulator:
    def __init__(self, config: SimulationConfig):
        self.config = config
        self.rng = random.Random(config.random_seed)
        self.p_damage, self.p_hole = compute_hit_probabilities(
            config.ship,
            config.battery.shell,
            config.battery.gun,
        )

    def run_trial(self, retreat_threshold: int) -> TrialResult:
        cfg = self.config
        battery = cfg.battery
        ship = cfg.ship
        repair = cfg.repair
        retreat = cfg.retreat

        hp = ship.max_hp
        flooding = 0.0
        active_holes = 0
        max_active_holes = 0
        time_s = 0.0

        next_shot_times = [0.0 for _ in range(battery.gun_count)]
        repair_finish_time: Optional[float] = None

        retreat_triggered = False
        retreat_reason = ""
        post_retreat_shots_remaining = (
            battery.gun_count * retreat.shells_per_gun_after_retreat
        )

        total_shells_fired = 0
        damaging_hits = 0
        holes_created = 0
        outcome = "timeout"
        survived = False

        def start_repair_if_possible(
            current_time: float,
        ) -> Optional[float]:
            if active_holes <= 0:
                return None
            return (
                current_time
                + repair.repair_time_for_holes(active_holes)
            )

        while time_s < cfg.max_time_s:
            shots_allowed = (
                not retreat_triggered
                or post_retreat_shots_remaining > 0
            )
            next_shot_time = (
                min(next_shot_times) if shots_allowed else math.inf
            )
            next_repair_time = (
                repair_finish_time
                if repair_finish_time is not None
                else math.inf
            )
            next_event_time = min(next_shot_time, next_repair_time)

            if next_event_time == math.inf:
                survived = hp > 0 and flooding < 1.0
                outcome = (
                    "survived_retreat"
                    if retreat_triggered
                    else "survived"
                )
                break

            dt = next_event_time - time_s
            if dt < -1e-9:
                raise RuntimeError("Negative time step detected.")

            net_holes = max(
                0, active_holes - cfg.power_bucketers
            )
            whole_ship_fill_time_per_hole = (
                ship.seconds_per_hole_to_fill_one_compartment
                * ship.compartment_count
            )
            if net_holes > 0:
                flooding += (
                    dt * net_holes
                    / whole_ship_fill_time_per_hole
                )

            time_s = next_event_time

            if flooding >= 1.0:
                flooding = 1.0
                outcome = "flooding_death"
                break
            if hp <= 0:
                outcome = "hp_death"
                break

            if (
                repair_finish_time is not None
                and abs(time_s - repair_finish_time) < 1e-9
            ):
                if active_holes > 0:
                    active_holes -= 1
                repair_finish_time = start_repair_if_possible(
                    time_s
                )

            shot_indices = [
                index
                for index, shot_time in enumerate(next_shot_times)
                if abs(shot_time - time_s) < 1e-9
            ]

            for index in shot_indices:
                if retreat_triggered:
                    if post_retreat_shots_remaining <= 0:
                        next_shot_times[index] = math.inf
                        continue
                    post_retreat_shots_remaining -= 1

                total_shells_fired += 1

                if self.rng.random() < self.p_damage:
                    hp -= battery.shell.effective_damage
                    damaging_hits += 1

                if self.rng.random() < self.p_hole:
                    active_holes += 1
                    holes_created += 1
                    max_active_holes = max(
                        max_active_holes, active_holes
                    )
                    if repair_finish_time is None:
                        repair_finish_time = (
                            start_repair_if_possible(time_s)
                        )

                next_shot_times[index] = (
                    time_s + battery.gun.cycle_time_s
                )

            if hp <= 0:
                hp = 0.0
                outcome = "hp_death"
                break

            if not retreat_triggered:
                hp_fraction = (
                    hp / ship.max_hp if ship.max_hp > 0 else 0
                )
                if hp_fraction <= retreat.hp_retreat_fraction:
                    retreat_triggered = True
                    retreat_reason = "hp"
                elif active_holes >= retreat_threshold:
                    retreat_triggered = True
                    retreat_reason = "holes"

                if retreat_triggered:
                    post_retreat_shots_remaining = (
                        battery.gun_count
                        * retreat.shells_per_gun_after_retreat
                    )

            if (
                retreat_triggered
                and post_retreat_shots_remaining <= 0
            ):
                next_shot_times = [
                    math.inf for _ in next_shot_times
                ]

            if (
                retreat_triggered
                and post_retreat_shots_remaining <= 0
                and active_holes <= 0
            ):
                survived = hp > 0 and flooding < 1.0
                outcome = (
                    "survived_retreat" if survived else outcome
                )
                break

        if time_s >= cfg.max_time_s and outcome == "timeout":
            survived = hp > 0 and flooding < 1.0
            outcome = (
                "timeout_alive" if survived else "timeout_dead"
            )

        return TrialResult(
            retreat_threshold=retreat_threshold,
            survived=survived,
            outcome=outcome,
            time_s=time_s,
            hp_left=max(0.0, hp),
            active_holes_end=active_holes,
            flooding_fraction_end=min(1.0, flooding),
            max_active_holes=max_active_holes,
            retreat_triggered=retreat_triggered,
            retreat_reason=retreat_reason,
            total_shells_fired=total_shells_fired,
            damaging_hits=damaging_hits,
            holes_created=holes_created,
        )

    def run_batches(
        self,
    ) -> Tuple[List[SummaryResult], List[TrialResult]]:
        cfg = self.config
        summaries: List[SummaryResult] = []
        all_trials: List[TrialResult] = []

        for threshold in range(
            cfg.retreat.leak_threshold_low,
            cfg.retreat.leak_threshold_high + 1,
        ):
            trials = [
                self.run_trial(threshold)
                for _ in range(
                    cfg.batch_size_per_threshold
                )
            ]
            all_trials.extend(trials)
            summaries.append(
                summarize_trials(threshold, trials)
            )

        return summaries, all_trials


def summarize_trials(
    threshold: int, trials: List[TrialResult]
) -> SummaryResult:
    n = len(trials)
    if n == 0:
        raise ValueError("Cannot summarize zero trials.")

    def pct(predicate) -> float:
        return (
            100.0
            * sum(1 for trial in trials if predicate(trial))
            / n
        )

    return SummaryResult(
        retreat_threshold=threshold,
        simulations=n,
        survival_pct=pct(lambda trial: trial.survived),
        flooding_death_pct=pct(
            lambda trial: trial.outcome == "flooding_death"
        ),
        hp_death_pct=pct(
            lambda trial: trial.outcome == "hp_death"
        ),
        avg_time_s=statistics.mean(
            trial.time_s for trial in trials
        ),
        median_time_s=statistics.median(
            trial.time_s for trial in trials
        ),
        avg_hp_left=statistics.mean(
            trial.hp_left for trial in trials
        ),
        avg_active_holes_end=statistics.mean(
            trial.active_holes_end for trial in trials
        ),
        avg_flooding_pct_end=100.0
        * statistics.mean(
            trial.flooding_fraction_end for trial in trials
        ),
        avg_max_holes=statistics.mean(
            trial.max_active_holes for trial in trials
        ),
        avg_shells_fired=statistics.mean(
            trial.total_shells_fired for trial in trials
        ),
        avg_damaging_hits=statistics.mean(
            trial.damaging_hits for trial in trials
        ),
        avg_holes_created=statistics.mean(
            trial.holes_created for trial in trials
        ),
    )
