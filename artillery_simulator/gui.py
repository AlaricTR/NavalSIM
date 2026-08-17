"""Tkinter user interface for the artillery simulator."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Dict, List

from .data_loader import build_shell_type, load_artillery_data, resolve_data_path
from .duel_simulation import DuelEngagementSimulator
from .formatting import format_duel_summary_table, format_summary_table
from .geometry import (
    NAVAL_MAX_RANGE_M,
    NAVAL_MAX_SPREAD_M,
    NAVAL_MIN_RANGE_M,
    NAVAL_MIN_SPREAD_M,
    compute_hit_probabilities,
    naval_spread_at_range,
    rectangle_dimensions_from_area,
)
from .models import (
    BatteryModel,
    GunModel,
    RepairModel,
    RetreatRule,
    ShipDefinition,
    ShipModel,
    SimulationConfig,
)
from .simulation import EngagementSimulator
from .tooltip import ToolTip


class SimulatorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Artillery vs Ship Simulator v7")
        self.geometry("1380x850")
        self.minsize(1080, 700)

        (
            self.platforms,
            self.ships,
            self.shell_data,
            self.ship_resistance,
        ) = load_artillery_data(resolve_data_path())

        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self.vars: Dict[str, tk.StringVar] = {}
        self.platform_var = tk.StringVar()
        self.platform_info_var = tk.StringVar()
        self.ship_var = tk.StringVar()
        self.ship_info_var = tk.StringVar()
        self.duel_var = tk.BooleanVar(value=False)
        self.tooltips: List[ToolTip] = []

        self._build_ui()
        self.reset_defaults()

    def add_tooltip(self, widget: tk.Widget, text: str) -> None:
        self.tooltips.append(ToolTip(widget, text))

    def add_field(
        self,
        parent: ttk.Frame,
        label: str,
        key: str,
        default: str,
        row: int,
        help_text: str,
    ) -> ttk.Entry:
        label_widget = ttk.Label(parent, text=label)
        label_widget.grid(row=row, column=0, sticky="w", padx=6, pady=3)
        variable = tk.StringVar(value=default)
        self.vars[key] = variable
        entry = ttk.Entry(parent, textvariable=variable, width=14)
        entry.grid(row=row, column=1, sticky="ew", padx=6, pady=3)
        self.add_tooltip(label_widget, help_text)
        self.add_tooltip(entry, help_text)
        return entry

    def _section(self, parent: ttk.Frame, title: str, row: int) -> int:
        if row > 0:
            ttk.Separator(parent).grid(
                row=row, column=0, columnspan=2, sticky="ew", pady=8
            )
            row += 1
        ttk.Label(
            parent,
            text=title,
            font=("TkDefaultFont", 10, "bold"),
        ).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(0, 6),
        )
        return row + 1

    def _build_ui(self) -> None:
        input_frame = ttk.Frame(self, padding=10)
        input_frame.grid(row=0, column=0, sticky="nsw")
        input_frame.columnconfigure(1, weight=1)

        row = self._section(input_frame, "Battery / Platform", 0)

        platform_label = ttk.Label(input_frame, text="Artillery platform")
        platform_label.grid(row=row, column=0, sticky="w", padx=6, pady=3)
        self.platform_combo = ttk.Combobox(
            input_frame,
            textvariable=self.platform_var,
            values=list(self.platforms.keys()),
            state="readonly",
            width=18,
        )
        self.platform_combo.grid(row=row, column=1, sticky="ew", padx=6, pady=3)
        self.platform_combo.bind("<<ComboboxSelected>>", self.on_platform_changed)
        platform_help = (
            "Loads the battery's range, spread, shell, HP, resistance, spacing, "
            "and deployment type from the JSON data file."
        )
        self.add_tooltip(platform_label, platform_help)
        self.add_tooltip(self.platform_combo, platform_help)
        row += 1

        self.add_field(
            input_frame,
            "Battery size",
            "battery_size",
            "3",
            row,
            "Number of guns in the straight-line battery formation.",
        )
        row += 1
        self.add_field(
            input_frame,
            "Engagement range (m)",
            "engagement_range",
            "250",
            row,
            "Distance between ship and battery. Spread is clamped to the nearest listed endpoint outside a weapon's range.",
        )
        row += 1

        self.duel_check = ttk.Checkbutton(
            input_frame,
            text="Ship fires at battery (duel)",
            variable=self.duel_var,
            command=self.on_duel_toggled,
        )
        self.duel_check.grid(
            row=row, column=0, columnspan=2, sticky="w", padx=6, pady=(5, 3)
        )
        self.add_tooltip(
            self.duel_check,
            "When enabled, the ship fires at individual guns and destroyed guns stop firing. This adds the Duel Results tab and uses the mutual-combat simulator.",
        )
        row += 1

        ttk.Label(
            input_frame,
            textvariable=self.platform_info_var,
            justify="left",
            wraplength=315,
        ).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            padx=6,
            pady=(4, 2),
        )
        row += 1

        row = self._section(input_frame, "Ship", row)
        ship_label = ttk.Label(input_frame, text="Ship model")
        ship_label.grid(row=row, column=0, sticky="w", padx=6, pady=3)
        self.ship_combo = ttk.Combobox(
            input_frame,
            textvariable=self.ship_var,
            values=list(self.ships.keys()),
            state="readonly",
            width=18,
        )
        self.ship_combo.grid(row=row, column=1, sticky="ew", padx=6, pady=3)
        self.ship_combo.bind("<<ComboboxSelected>>", self.on_ship_changed)
        ship_help = (
            "Loads the target ship's HP, area, compartments, flooding rate, "
            "turret count, reload, and shells per turret."
        )
        self.add_tooltip(ship_label, ship_help)
        self.add_tooltip(self.ship_combo, ship_help)
        row += 1

        ttk.Label(
            input_frame,
            textvariable=self.ship_info_var,
            justify="left",
            wraplength=315,
        ).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            padx=6,
            pady=(4, 2),
        )
        row += 1

        self.add_field(
            input_frame,
            "Length:width ratio",
            "ship_ratio",
            f"{60 / 11:.4f}",
            row,
            "Controls the rectangular shape used for the ship's hit-area approximation.",
        )
        row += 1

        row = self._section(input_frame, "Damage Control", row)
        damage_fields = [
            (
                "Min leak repair time (s)",
                "repair_min",
                "30",
                "Estimated time to fix a wet leak when the ship is completely dry.",
            ),
            (
                "Max leak repair time (s)",
                "repair_max",
                "60",
                "Estimated time to fix a wet leak when the ship is actively flooding and the damage-control crew is in chaos.",
            ),
            (
                "Power bucketers",
                "power_bucketers",
                "2",
                "Each pumping unit offsets roughly one active leak's flooding flow.",
            ),
        ]
        for label, key, default, help_text in damage_fields:
            self.add_field(input_frame, label, key, default, row, help_text)
            row += 1

        row = self._section(input_frame, "Retreat / Batch", row)
        retreat_fields = [
            (
                "Retreat holes low",
                "retreat_low",
                "8",
                "Lowest active-hole retreat threshold to test.",
            ),
            (
                "Retreat holes high",
                "retreat_high",
                "15",
                "Highest active-hole retreat threshold to test. Every integer threshold in the range is simulated.",
            ),
            (
                "HP retreat threshold %",
                "hp_retreat_pct",
                "30",
                "The ship starts retreating when remaining HP reaches this percentage.",
            ),
            (
                "Post-retreat shots / gun",
                "post_retreat_shots",
                "3",
                "Additional shells each surviving battery gun may fire after retreat begins.",
            ),
            (
                "Batch size / threshold",
                "batch_size",
                "1000",
                "Number of Monte Carlo trials for each wet-hole retreat threshold.",
            ),
            (
                "Random seed blank=random",
                "random_seed",
                "",
                "Optional fixed seed for repeatable results. Leave blank for a new random sequence.",
            ),
        ]
        for label, key, default, help_text in retreat_fields:
            self.add_field(input_frame, label, key, default, row, help_text)
            row += 1

        ttk.Button(
            input_frame, text="Run simulation", command=self.run_simulation
        ).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=6,
            pady=(12, 4),
        )
        row += 1
        ttk.Button(
            input_frame,
            text="Reset to current scenario",
            command=self.reset_defaults,
        ).grid(
            row=row, column=0, columnspan=2, sticky="ew", padx=6, pady=4
        )

        output_frame = ttk.Frame(self, padding=10)
        output_frame.grid(row=0, column=1, sticky="nsew")
        output_frame.rowconfigure(0, weight=1)
        output_frame.columnconfigure(0, weight=1)

        self.notebook = ttk.Notebook(output_frame)
        self.notebook.grid(row=0, column=0, sticky="nsew")

        self.ship_results_tab = ttk.Frame(self.notebook, padding=8)
        self.duel_results_tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(self.ship_results_tab, text="Ship Results")
        self._build_result_tab(
            self.ship_results_tab, "ship_summary_label", "ship_output"
        )
        self._build_result_tab(
            self.duel_results_tab, "duel_summary_label", "duel_output"
        )

    def _build_result_tab(
        self, parent: ttk.Frame, label_attr: str, text_attr: str
    ) -> None:
        parent.rowconfigure(1, weight=1)
        parent.columnconfigure(0, weight=1)
        label = ttk.Label(parent, text="Results will appear here.", justify="left")
        label.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        text = tk.Text(parent, wrap="none", font=("Consolas", 10))
        text.grid(row=1, column=0, sticky="nsew")
        y_scroll = ttk.Scrollbar(parent, orient="vertical", command=text.yview)
        y_scroll.grid(row=1, column=1, sticky="ns")
        x_scroll = ttk.Scrollbar(parent, orient="horizontal", command=text.xview)
        x_scroll.grid(row=2, column=0, sticky="ew")
        text.configure(
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set,
        )
        setattr(self, label_attr, label)
        setattr(self, text_attr, text)

    def _duel_tab_visible(self) -> bool:
        return str(self.duel_results_tab) in self.notebook.tabs()

    def on_duel_toggled(self) -> None:
        if self.duel_var.get() and not self._duel_tab_visible():
            self.notebook.add(self.duel_results_tab, text="Duel Results")
            self.duel_summary_label.config(
                text="Run the simulation to generate mutual-combat results."
            )
        elif not self.duel_var.get() and self._duel_tab_visible():
            self.notebook.forget(self.duel_results_tab)

    def selected_platform(self):
        key = self.platform_var.get()
        if key not in self.platforms:
            raise ValueError("Select an artillery platform.")
        return self.platforms[key]

    def selected_ship(self) -> ShipDefinition:
        key = self.ship_var.get()
        if key not in self.ships:
            raise ValueError("Select a ship model.")
        return self.ships[key]

    def on_platform_changed(self, _event=None) -> None:
        platform = self.selected_platform()
        shell = build_shell_type(
            platform.shell_type, self.shell_data, self.ship_resistance
        )
        if platform.deployment_type == "entrenched":
            protection = (
                f"Entrenched: {platform.entrenchment_radius_m:g}m vulnerable radius"
            )
        else:
            protection = (
                f"Pushgun: {platform.physical_width_m:g}m wide; shell blast radius applies"
            )
        self.platform_info_var.set(
            f"Range: {platform.min_range_m:g}–{platform.max_range_m:g}m | "
            f"Spread: {platform.min_spread_m:g}–{platform.max_spread_m:g}m\n"
            f"Cycle: {platform.cycle_time_s:g}s | Shell: {shell.name} | "
            f"Damage to ship: {shell.effective_damage:g}\n"
            f"HP / gun: {platform.max_hp:g} | Resistance: "
            f"{platform.damage_resistance * 100:.0f}% | "
            f"Spacing: {platform.center_spacing_m:g}m\n{protection}"
        )

    def on_ship_changed(self, _event=None) -> None:
        ship = self.selected_ship()
        total_shells = ship.turret_count * ship.shells_per_turret
        self.ship_info_var.set(
            f"HP: {ship.max_hp:g} | Area: {ship.area_m2:g}m² | "
            f"Compartments: {ship.compartment_count}\n"
            f"Flood time / compartment: "
            f"{ship.seconds_per_hole_to_fill_one_compartment:g}s | "
            f"Turrets: {ship.turret_count}\n"
            f"Reload: {ship.reload_time_per_turret_s:g}s | "
            f"Shells: {ship.shells_per_turret} / turret "
            f"({total_shells} per volley) | Type: {ship.turret_shell_type}\n"
            f"Naval spread: {NAVAL_MIN_SPREAD_M:g}–{NAVAL_MAX_SPREAD_M:g}m "
            f"at {NAVAL_MIN_RANGE_M:g}–{NAVAL_MAX_RANGE_M:g}m"
        )

    def reset_defaults(self) -> None:
        default_platform = (
            "Thunderbolt"
            if "Thunderbolt" in self.platforms
            else next(iter(self.platforms))
        )
        default_ship = (
            "Conqueror" if "Conqueror" in self.ships else next(iter(self.ships))
        )
        self.platform_var.set(default_platform)
        self.ship_var.set(default_ship)
        self.duel_var.set(False)
        defaults = {
            "battery_size": "3",
            "engagement_range": "250",
            "ship_ratio": f"{60 / 11:.4f}",
            "repair_min": "30",
            "repair_max": "60",
            "power_bucketers": "2",
            "retreat_low": "8",
            "retreat_high": "15",
            "hp_retreat_pct": "30",
            "post_retreat_shots": "3",
            "batch_size": "1000",
            "random_seed": "",
        }
        for key, value in defaults.items():
            self.vars[key].set(value)
        self.on_platform_changed()
        self.on_ship_changed()
        self.on_duel_toggled()

    def get_float(self, key: str) -> float:
        return float(self.vars[key].get().strip())

    def get_int(self, key: str) -> int:
        return int(float(self.vars[key].get().strip()))

    def build_config(self) -> SimulationConfig:
        seed_text = self.vars["random_seed"].get().strip()
        seed = int(seed_text) if seed_text else None
        platform = self.selected_platform()
        engagement_range = self.get_float("engagement_range")
        spread = platform.spread_at_range(engagement_range)
        battery_shell = build_shell_type(
            platform.shell_type, self.shell_data, self.ship_resistance
        )
        gun = GunModel(
            name=platform.name,
            spread_radius_m=spread,
            cycle_time_s=platform.cycle_time_s,
        )
        battery = BatteryModel(
            platform=platform,
            gun=gun,
            shell=battery_shell,
            gun_count=self.get_int("battery_size"),
            engagement_range_m=engagement_range,
        )

        selected_ship = self.selected_ship()
        ship = ShipModel(
            name=selected_ship.name,
            max_hp=selected_ship.max_hp,
            area_m2=selected_ship.area_m2,
            length_width_ratio=self.get_float("ship_ratio"),
            seconds_per_hole_to_fill_one_compartment=(
                selected_ship.seconds_per_hole_to_fill_one_compartment
            ),
            compartment_count=selected_ship.compartment_count,
            turret_count=selected_ship.turret_count,
            reload_time_per_turret_s=selected_ship.reload_time_per_turret_s,
            shells_per_turret=selected_ship.shells_per_turret,
            turret_shell_type=selected_ship.turret_shell_type,
        )
        repair = RepairModel(
            min_repair_time_s=self.get_float("repair_min"),
            max_repair_time_s=self.get_float("repair_max"),
        )
        retreat = RetreatRule(
            leak_threshold_low=self.get_int("retreat_low"),
            leak_threshold_high=self.get_int("retreat_high"),
            hp_retreat_fraction=self.get_float("hp_retreat_pct") / 100.0,
            shells_per_gun_after_retreat=self.get_int("post_retreat_shots"),
        )

        if engagement_range <= 0:
            raise ValueError("Engagement range must be positive.")
        if battery.gun_count <= 0:
            raise ValueError("Battery size must be positive.")
        if ship.length_width_ratio <= 0:
            raise ValueError("Length:width ratio must be positive.")
        if repair.min_repair_time_s <= 0 or (
            repair.max_repair_time_s < repair.min_repair_time_s
        ):
            raise ValueError("Repair times are invalid.")
        if retreat.leak_threshold_low <= 0:
            raise ValueError("Retreat hole thresholds must be positive.")
        if retreat.leak_threshold_low > retreat.leak_threshold_high:
            raise ValueError("Retreat holes low must be <= high.")
        if not 0.0 <= retreat.hp_retreat_fraction <= 1.0:
            raise ValueError("HP retreat threshold must be 0–100%.")
        if retreat.shells_per_gun_after_retreat < 0:
            raise ValueError("Post-retreat shots cannot be negative.")
        if self.get_int("power_bucketers") < 0:
            raise ValueError("Power bucketers cannot be negative.")
        if self.get_int("batch_size") <= 0:
            raise ValueError("Batch size must be positive.")

        return SimulationConfig(
            battery=battery,
            ship=ship,
            repair=repair,
            retreat=retreat,
            power_bucketers=self.get_int("power_bucketers"),
            batch_size_per_threshold=self.get_int("batch_size"),
            duel_enabled=self.duel_var.get(),
            random_seed=seed,
        )

    def _warn_for_long_range(self, engagement_range_m: float) -> None:
        if engagement_range_m > 250.0:
            messagebox.showwarning(
                "Long engagement range",
                "The engagement range is greater than 250m. The simulation will continue, but naval and platform spread values are clamped at their maximum-range values when necessary.",
            )

    def _ship_header(self, config: SimulationConfig, total_runs: int) -> str:
        p_damage, p_hole = compute_hit_probabilities(
            config.ship, config.battery.shell, config.battery.gun
        )
        length, width = rectangle_dimensions_from_area(
            config.ship.area_m2, config.ship.length_width_ratio
        )
        platform = config.battery.platform
        mode = (
            "Mutual duel: the ship attacks individual guns"
            if config.duel_enabled
            else "Battery-only: the ship does not return fire"
        )
        return (
            f"Mode: {mode}\n"
            f"Platform: {platform.name}\n"
            f"Ship: {config.ship.name}\n"
            f"Battery size: {config.battery.gun_count}\n"
            f"Engagement range: {config.battery.engagement_range_m:g}m\n"
            f"Battery spread radius: {config.battery.gun.spread_radius_m:.2f}m\n"
            f"Battery firing cycle: {platform.cycle_time_s:g}s\n"
            f"Battery shell: {config.battery.shell.name}; effective ship damage: "
            f"{config.battery.shell.effective_damage:g}\n"
            f"Total simulations: {total_runs}\n"
            f"Ship rectangle: {length:.1f}m x {width:.1f}m = "
            f"{config.ship.area_m2:.1f}m²\n"
            f"Damage chance per battery shell: {p_damage * 100:.2f}%\n"
            f"Wet-hole chance per battery shell: {p_hole * 100:.2f}%\n"
            f"Power bucketers: {config.power_bucketers}\n"
            f"HP retreat threshold: "
            f"{config.retreat.hp_retreat_fraction * 100:.1f}% remaining\n"
        )

    def _duel_header(self, config: SimulationConfig) -> str:
        platform = config.battery.platform
        naval_spread = naval_spread_at_range(config.battery.engagement_range_m)
        vulnerable = (
            f"4m trench circle"
            if platform.deployment_type == "entrenched"
            else f"{config.ship.turret_shell_type} blast radius"
        )
        return (
            f"Battery: {platform.name}; {config.battery.gun_count} guns in a line\n"
            f"Gun HP: {platform.max_hp:g} each | Resistance: "
            f"{platform.damage_resistance * 100:.0f}% | "
            f"Center spacing: {platform.center_spacing_m:g}m\n"
            f"Gun vulnerability: {vulnerable}\n"
            f"Ship volley: {config.ship.turret_count} turrets x "
            f"{config.ship.shells_per_turret} shells; reload "
            f"{config.ship.reload_time_per_turret_s:g}s\n"
            f"Naval shell: {config.ship.turret_shell_type} | "
            f"Naval spread at range: {naval_spread:.2f}m\n"
            f"Retarget delay when a better aim group is required: 5–10s\n"
            f"A dead battery means every gun has reached 0 HP.\n"
            f"The fixed HP retreat threshold is "
            f"{config.retreat.hp_retreat_fraction * 100:.1f}%; rows vary the hole threshold.\n"
        )

    def run_simulation(self) -> None:
        try:
            config = self.build_config()
            self._warn_for_long_range(config.battery.engagement_range_m)
            threshold_count = (
                config.retreat.leak_threshold_high
                - config.retreat.leak_threshold_low
                + 1
            )
            total_runs = config.batch_size_per_threshold * threshold_count

            duel_summaries = None
            if config.duel_enabled:
                naval_shell = build_shell_type(
                    config.ship.turret_shell_type,
                    self.shell_data,
                    0.0,
                )
                simulator = DuelEngagementSimulator(config, naval_shell)
                ship_summaries, duel_summaries, _ = simulator.run_batches()
            else:
                simulator = EngagementSimulator(config)
                ship_summaries, _ = simulator.run_batches()

            self.ship_summary_label.config(
                text=(
                    f"Ran {total_runs} simulations with {config.battery.platform.name} "
                    f"({config.batch_size_per_threshold} per hole threshold)."
                )
            )
            self.ship_output.delete("1.0", tk.END)
            self.ship_output.insert(
                tk.END,
                self._ship_header(config, total_runs)
                + "\n"
                + format_summary_table(ship_summaries),
            )

            if config.duel_enabled and duel_summaries is not None:
                if not self._duel_tab_visible():
                    self.notebook.add(self.duel_results_tab, text="Duel Results")
                self.duel_summary_label.config(
                    text=(
                        f"Mutual-combat outcomes across {total_runs} simulations. "
                        "Time in fight ends when retreat, battery destruction, ship destruction, or timeout resolves the duel."
                    )
                )
                self.duel_output.delete("1.0", tk.END)
                self.duel_output.insert(
                    tk.END,
                    self._duel_header(config)
                    + "\n"
                    + format_duel_summary_table(duel_summaries),
                )
            else:
                self.duel_output.delete("1.0", tk.END)

        except Exception as error:
            messagebox.showerror("Simulation error", str(error))
