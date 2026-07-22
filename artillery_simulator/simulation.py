"""Battery-only Monte Carlo engagement engine and trial summarization."""
from __future__ import annotations

import math
import random
import statistics
from typing import List, Tuple

from .geometry import compute_hit_probabilities
from .models import SimulationConfig, SummaryResult, TrialResult
from .ship_state import ShipCombatState


class EngagementSimulator:
    """Existing one-way mode: the battery fires and the ship does not return fire."""

    def __init__(self, config: SimulationConfig):
        self.config = config
        self.rng = random.Random(config.random_seed)
        self.p_damage, self.p_hole = compute_hit_probabilities(
            config.ship, config.battery.shell, config.battery.gun
        )

    def run_trial(self, retreat_threshold: int) -> TrialResult:
        cfg = self.config
        state = ShipCombatState.new(cfg.ship)
        time_s = 0.0
        next_shot_times = [0.0 for _ in range(cfg.battery.gun_count)]
        retreat_triggered = False
        retreat_reason = ""
        post_retreat_remaining = [
            cfg.retreat.shells_per_gun_after_retreat
            for _ in range(cfg.battery.gun_count)
        ]

        total_shells_fired = 0
        damaging_hits = 0
        holes_created = 0
        outcome = "timeout"
        survived = False

        while time_s < cfg.max_time_s:
            next_shot = min(next_shot_times, default=math.inf)
            next_repair = (
                state.repair_finish_time
                if state.repair_finish_time is not None
                else math.inf
            )
            next_event = min(next_shot, next_repair)

            if next_event == math.inf:
                survived = state.death_outcome() is None
                outcome = "survived_retreat" if retreat_triggered else "survived"
                break

            dt = next_event - time_s
            if dt < -1e-9:
                raise RuntimeError("Negative time step detected.")
            state.advance_flooding(dt, cfg.ship, cfg.power_bucketers)
            time_s = next_event

            death = state.death_outcome()
            if death:
                outcome = death
                break

            if (
                state.repair_finish_time is not None
                and abs(time_s - state.repair_finish_time) < 1e-9
            ):
                state.finish_repair(time_s, cfg.repair)

            shot_indices = [
                index
                for index, shot_time in enumerate(next_shot_times)
                if abs(shot_time - time_s) < 1e-9
            ]
            for index in shot_indices:
                if retreat_triggered:
                    if post_retreat_remaining[index] <= 0:
                        next_shot_times[index] = math.inf
                        continue
                    post_retreat_remaining[index] -= 1

                total_shells_fired += 1
                hit, hole = state.apply_probabilistic_shell(
                    self.rng,
                    self.p_damage,
                    self.p_hole,
                    cfg.battery.shell,
                    time_s,
                    cfg.repair,
                )
                damaging_hits += int(hit)
                holes_created += int(hole)

                if retreat_triggered and post_retreat_remaining[index] <= 0:
                    next_shot_times[index] = math.inf
                else:
                    next_shot_times[index] = time_s + cfg.battery.gun.cycle_time_s

            death = state.death_outcome()
            if death:
                outcome = death
                break

            if not retreat_triggered:
                hp_fraction = state.hp / cfg.ship.max_hp
                if hp_fraction <= cfg.retreat.hp_retreat_fraction:
                    retreat_triggered = True
                    retreat_reason = "hp"
                elif state.active_holes >= retreat_threshold:
                    retreat_triggered = True
                    retreat_reason = "holes"

            if (
                retreat_triggered
                and all(value <= 0 for value in post_retreat_remaining)
                and state.active_holes <= 0
            ):
                survived = state.death_outcome() is None
                outcome = "survived_retreat" if survived else outcome
                break

        if time_s >= cfg.max_time_s and outcome == "timeout":
            survived = state.death_outcome() is None
            outcome = "timeout_alive" if survived else "timeout_dead"

        return TrialResult(
            retreat_threshold=retreat_threshold,
            survived=survived,
            outcome=outcome,
            time_s=time_s,
            hp_left=max(0.0, state.hp),
            active_holes_end=state.active_holes,
            flooding_fraction_end=min(1.0, state.flooding),
            max_active_holes=state.max_active_holes,
            retreat_triggered=retreat_triggered,
            retreat_reason=retreat_reason,
            total_shells_fired=total_shells_fired,
            damaging_hits=damaging_hits,
            holes_created=holes_created,
        )

    def run_batches(self) -> Tuple[List[SummaryResult], List[TrialResult]]:
        summaries: List[SummaryResult] = []
        all_trials: List[TrialResult] = []
        for threshold in range(
            self.config.retreat.leak_threshold_low,
            self.config.retreat.leak_threshold_high + 1,
        ):
            trials = [
                self.run_trial(threshold)
                for _ in range(self.config.batch_size_per_threshold)
            ]
            all_trials.extend(trials)
            summaries.append(summarize_trials(threshold, trials))
        return summaries, all_trials


def summarize_trials(
    threshold: int, trials: List[TrialResult]
) -> SummaryResult:
    if not trials:
        raise ValueError("Cannot summarize zero trials.")
    n = len(trials)

    def pct(predicate) -> float:
        return 100.0 * sum(1 for trial in trials if predicate(trial)) / n

    return SummaryResult(
        retreat_threshold=threshold,
        simulations=n,
        survival_pct=pct(lambda trial: trial.survived),
        flooding_death_pct=pct(lambda trial: trial.outcome == "flooding_death"),
        hp_death_pct=pct(lambda trial: trial.outcome == "hp_death"),
        avg_time_s=statistics.mean(trial.time_s for trial in trials),
        median_time_s=statistics.median(trial.time_s for trial in trials),
        avg_hp_left=statistics.mean(trial.hp_left for trial in trials),
        avg_active_holes_end=statistics.mean(
            trial.active_holes_end for trial in trials
        ),
        avg_flooding_pct_end=100.0
        * statistics.mean(trial.flooding_fraction_end for trial in trials),
        avg_max_holes=statistics.mean(trial.max_active_holes for trial in trials),
        avg_shells_fired=statistics.mean(
            trial.total_shells_fired for trial in trials
        ),
        avg_damaging_hits=statistics.mean(trial.damaging_hits for trial in trials),
        avg_holes_created=statistics.mean(trial.holes_created for trial in trials),
    )
