"""Tkinter user interface for the artillery simulator."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Dict, List

from .data_loader import build_shell_type, load_artillery_data, resolve_data_path
from .formatting import format_summary_table
from .geometry import compute_hit_probabilities, rectangle_dimensions_from_area
from .models import (
    ArtilleryPlatform, BatteryModel, GunModel, RepairModel,
    RetreatRule, ShipDefinition, ShipModel, SimulationConfig,
)
from .simulation import EngagementSimulator
from .tooltip import ToolTip

class SimulatorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Artillery vs Ship Simulator v5")
        self.geometry("1280x780")
        self.minsize(1000, 650)

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
        self.tooltips: List[ToolTip] = []

        self._build_ui()
        self.reset_defaults()

    def add_tooltip(
        self,
        widget: tk.Widget,
        text: str,
    ) -> None:
        self.tooltips.append(ToolTip(widget, text))

    def add_field(
        self,
        parent,
        label: str,
        key: str,
        default: str,
        row: int,
        help_text: str,
    ):
        label_widget = ttk.Label(parent, text=label)
        label_widget.grid(
            row=row,
            column=0,
            sticky="w",
            padx=6,
            pady=3,
        )
        variable = tk.StringVar(value=default)
        self.vars[key] = variable
        entry = ttk.Entry(
            parent,
            textvariable=variable,
            width=14,
        )
        entry.grid(
            row=row,
            column=1,
            sticky="ew",
            padx=6,
            pady=3,
        )
        self.add_tooltip(label_widget, help_text)
        self.add_tooltip(entry, help_text)
        return entry

    def _build_ui(self):
        input_frame = ttk.Frame(self, padding=10)
        input_frame.grid(row=0, column=0, sticky="nsw")
        input_frame.columnconfigure(1, weight=1)

        row = 0
        ttk.Label(
            input_frame,
            text="Battery / Platform",
            font=("TkDefaultFont", 10, "bold"),
        ).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(0, 6),
        )
        row += 1

        platform_label = ttk.Label(
            input_frame, text="Artillery platform"
        )
        platform_label.grid(
            row=row,
            column=0,
            sticky="w",
            padx=6,
            pady=3,
        )
        self.platform_combo = ttk.Combobox(
            input_frame,
            textvariable=self.platform_var,
            values=list(self.platforms.keys()),
            state="readonly",
            width=18,
        )
        self.platform_combo.grid(
            row=row,
            column=1,
            sticky="ew",
            padx=6,
            pady=3,
        )
        self.platform_combo.bind(
            "<<ComboboxSelected>>",
            self.on_platform_changed,
        )
        platform_help = (
            "Selects the artillery platform and loads its range, "
            "spread, firing cycle, and shell type from the data file."
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
            "Number of artillery guns firing at the ship.",
        )
        row += 1
        self.add_field(
            input_frame,
            "Engagement range (m)",
            "engagement_range",
            "350",
            row,
            "Distance from the battery to the ship. This determines the gun's interpolated spread.",
        )
        row += 1

        ttk.Label(
            input_frame,
            textvariable=self.platform_info_var,
            justify="left",
            wraplength=270,
        ).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            padx=6,
            pady=(4, 2),
        )
        row += 1

        ttk.Separator(input_frame).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=8,
        )
        row += 1
        ttk.Label(
            input_frame,
            text="Ship",
            font=("TkDefaultFont", 10, "bold"),
        ).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(0, 6),
        )
        row += 1

        ship_label = ttk.Label(input_frame, text="Ship model")
        ship_label.grid(
            row=row,
            column=0,
            sticky="w",
            padx=6,
            pady=3,
        )
        self.ship_combo = ttk.Combobox(
            input_frame,
            textvariable=self.ship_var,
            values=list(self.ships.keys()),
            state="readonly",
            width=18,
        )
        self.ship_combo.grid(
            row=row,
            column=1,
            sticky="ew",
            padx=6,
            pady=3,
        )
        self.ship_combo.bind(
            "<<ComboboxSelected>>",
            self.on_ship_changed,
        )
        ship_help = (
            "Selects the target ship and loads its HP, area, "
            "compartments, flooding rate, and turret data."
        )
        self.add_tooltip(ship_label, ship_help)
        self.add_tooltip(self.ship_combo, ship_help)
        row += 1

        ttk.Label(
            input_frame,
            textvariable=self.ship_info_var,
            justify="left",
            wraplength=270,
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

        ttk.Separator(input_frame).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=8,
        )
        row += 1
        ttk.Label(
            input_frame,
            text="Damage Control",
            font=("TkDefaultFont", 10, "bold"),
        ).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(0, 6),
        )
        row += 1

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
                "Number of pumping units. Each offsets roughly one active leak's flooding flow.",
            ),
        ]
        for label, key, default, help_text in damage_fields:
            self.add_field(
                input_frame,
                label,
                key,
                default,
                row,
                help_text,
            )
            row += 1

        ttk.Separator(input_frame).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=8,
        )
        row += 1
        ttk.Label(
            input_frame,
            text="Retreat / Batch",
            font=("TkDefaultFont", 10, "bold"),
        ).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(0, 6),
        )
        row += 1

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
                "Highest active-hole retreat threshold to test. Every whole-number threshold in the range is simulated.",
            ),
            (
                "HP retreat threshold %",
                "hp_retreat_pct",
                "30",
                "The ship begins retreating when its remaining HP falls to this percentage.",
            ),
            (
                "Post-retreat shots / gun",
                "post_retreat_shots",
                "3",
                "Additional shells each enemy gun may fire after the ship begins retreating.",
            ),
            (
                "Batch size / threshold",
                "batch_size",
                "1000",
                "Number of Monte Carlo trials run for each wet-hole retreat threshold.",
            ),
            (
                "Random seed blank=random",
                "random_seed",
                "",
                "Optional fixed seed for repeatable results. Leave blank for a new random sequence.",
            ),
        ]
        for label, key, default, help_text in retreat_fields:
            self.add_field(
                input_frame,
                label,
                key,
                default,
                row,
                help_text,
            )
            row += 1

        ttk.Button(
            input_frame,
            text="Run simulation",
            command=self.run_simulation,
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
            row=row,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=6,
            pady=4,
        )

        output_frame = ttk.Frame(self, padding=10)
        output_frame.grid(row=0, column=1, sticky="nsew")
        output_frame.rowconfigure(1, weight=1)
        output_frame.columnconfigure(0, weight=1)

        self.summary_label = ttk.Label(
            output_frame,
            text="Results will appear here.",
            justify="left",
        )
        self.summary_label.grid(
            row=0,
            column=0,
            sticky="ew",
            pady=(0, 8),
        )

        self.output = tk.Text(
            output_frame,
            wrap="none",
            font=("Consolas", 10),
        )
        self.output.grid(
            row=1,
            column=0,
            sticky="nsew",
        )

        y_scroll = ttk.Scrollbar(
            output_frame,
            orient="vertical",
            command=self.output.yview,
        )
        y_scroll.grid(row=1, column=1, sticky="ns")
        self.output.configure(
            yscrollcommand=y_scroll.set
        )

        x_scroll = ttk.Scrollbar(
            output_frame,
            orient="horizontal",
            command=self.output.xview,
        )
        x_scroll.grid(row=2, column=0, sticky="ew")
        self.output.configure(
            xscrollcommand=x_scroll.set
        )

    def selected_platform(self) -> ArtilleryPlatform:
        key = self.platform_var.get()
        if key not in self.platforms:
            raise ValueError("Select an artillery platform.")
        return self.platforms[key]

    def on_platform_changed(self, _event=None):
        platform = self.selected_platform()
        shell = build_shell_type(
            platform.shell_type,
            self.shell_data,
            self.ship_resistance,
        )

        self.platform_info_var.set(
            f"Range: {platform.min_range_m:g}–"
            f"{platform.max_range_m:g}m | "
            f"Spread: {platform.min_spread_m:g}–"
            f"{platform.max_spread_m:g}m\n"
            f"Cycle: {platform.firing_time_s:g}s firing + "
            f"{platform.reload_time_s:g}s reload = "
            f"{platform.cycle_time_s:g}s | "
            f"Shell: {shell.name} | "
            f"Effective damage: {shell.effective_damage:g}"
        )

        range_var = self.vars.get("engagement_range")
        if range_var is not None:
            try:
                current_range = float(
                    range_var.get().strip()
                )
            except ValueError:
                current_range = platform.max_range_m

            if not (
                platform.min_range_m
                <= current_range
                <= platform.max_range_m
            ):
                range_var.set(
                    f"{platform.max_range_m:g}"
                )

    def selected_ship(self) -> ShipDefinition:
        key = self.ship_var.get()
        if key not in self.ships:
            raise ValueError("Select a ship model.")
        return self.ships[key]

    def on_ship_changed(self, _event=None):
        ship = self.selected_ship()
        total_shells = ship.turret_count * ship.shells_per_turret
        self.ship_info_var.set(
            f"HP: {ship.max_hp:g} | Area: {ship.area_m2:g}m² | "
            f"Compartments: {ship.compartment_count}\n"
            f"Flood time / compartment: "
            f"{ship.seconds_per_hole_to_fill_one_compartment:g}s | "
            f"Turrets: {ship.turret_count} | "
            f"Reload: {ship.reload_time_per_turret_s:g}s / turret | "
            f"Shells: {ship.shells_per_turret} / turret "
            f"({total_shells} total per full volley)"
        )

    def reset_defaults(self):
        default_platform = (
            "Thunderbolt"
            if "Thunderbolt" in self.platforms
            else next(iter(self.platforms))
        )
        self.platform_var.set(default_platform)
        default_ship = (
            "Conqueror"
            if "Conqueror" in self.ships
            else next(iter(self.ships))
        )
        self.ship_var.set(default_ship)

        defaults = {
            "battery_size": "3",
            "engagement_range": (
                f"{self.platforms[default_platform].max_range_m:g}"
            ),
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

    def get_float(self, key: str) -> float:
        return float(self.vars[key].get().strip())

    def get_int(self, key: str) -> int:
        return int(float(self.vars[key].get().strip()))

    def build_config(self) -> SimulationConfig:
        seed_text = self.vars["random_seed"].get().strip()
        seed = int(seed_text) if seed_text else None

        platform = self.selected_platform()
        engagement_range = self.get_float(
            "engagement_range"
        )
        spread = platform.spread_at_range(
            engagement_range
        )
        shell = build_shell_type(
            platform.shell_type,
            self.shell_data,
            self.ship_resistance,
        )

        gun = GunModel(
            name=platform.name,
            spread_radius_m=spread,
            cycle_time_s=platform.cycle_time_s,
        )
        battery = BatteryModel(
            platform=platform,
            gun=gun,
            shell=shell,
            gun_count=self.get_int("battery_size"),
            engagement_range_m=engagement_range,
        )

        selected_ship = self.selected_ship()
        ship = ShipModel(
            name=selected_ship.name,
            max_hp=selected_ship.max_hp,
            area_m2=selected_ship.area_m2,
            length_width_ratio=self.get_float(
                "ship_ratio"
            ),
            seconds_per_hole_to_fill_one_compartment=(
                selected_ship.seconds_per_hole_to_fill_one_compartment
            ),
            compartment_count=selected_ship.compartment_count,
        )

        repair = RepairModel(
            min_repair_time_s=self.get_float(
                "repair_min"
            ),
            max_repair_time_s=self.get_float(
                "repair_max"
            ),
        )
        retreat = RetreatRule(
            leak_threshold_low=self.get_int(
                "retreat_low"
            ),
            leak_threshold_high=self.get_int(
                "retreat_high"
            ),
            hp_retreat_fraction=self.get_float(
                "hp_retreat_pct"
            )
            / 100.0,
            shells_per_gun_after_retreat=self.get_int(
                "post_retreat_shots"
            ),
        )

        if battery.gun_count <= 0:
            raise ValueError("Battery size must be positive.")
        if ship.max_hp <= 0 or ship.area_m2 <= 0:
            raise ValueError(
                "Ship health and area must be positive."
            )
        if ship.length_width_ratio <= 0:
            raise ValueError(
                "Length:width ratio must be positive."
            )
        if ship.compartment_count <= 0:
            raise ValueError(
                "Compartment count must be positive."
            )
        if (
            ship.seconds_per_hole_to_fill_one_compartment
            <= 0
        ):
            raise ValueError(
                "Flooding time must be positive."
            )
        if (
            repair.min_repair_time_s <= 0
            or repair.max_repair_time_s
            < repair.min_repair_time_s
        ):
            raise ValueError(
                "Repair times are invalid."
            )
        if retreat.leak_threshold_low <= 0:
            raise ValueError(
                "Retreat hole thresholds must be positive."
            )
        if (
            retreat.leak_threshold_low
            > retreat.leak_threshold_high
        ):
            raise ValueError(
                "Retreat holes low must be <= high."
            )
        if not 0.0 <= retreat.hp_retreat_fraction <= 1.0:
            raise ValueError(
                "HP retreat threshold must be 0–100%."
            )
        if retreat.shells_per_gun_after_retreat < 0:
            raise ValueError(
                "Post-retreat shots cannot be negative."
            )
        if self.get_int("power_bucketers") < 0:
            raise ValueError(
                "Power bucketers cannot be negative."
            )
        if self.get_int("batch_size") <= 0:
            raise ValueError(
                "Batch size must be positive."
            )

        return SimulationConfig(
            battery=battery,
            ship=ship,
            repair=repair,
            retreat=retreat,
            power_bucketers=self.get_int(
                "power_bucketers"
            ),
            batch_size_per_threshold=self.get_int(
                "batch_size"
            ),
            random_seed=seed,
        )

    def run_simulation(self):
        try:
            config = self.build_config()
            simulator = EngagementSimulator(config)
            summaries, _ = simulator.run_batches()

            threshold_count = (
                config.retreat.leak_threshold_high
                - config.retreat.leak_threshold_low
                + 1
            )
            total_runs = (
                config.batch_size_per_threshold
                * threshold_count
            )

            p_damage, p_hole = compute_hit_probabilities(
                config.ship,
                config.battery.shell,
                config.battery.gun,
            )
            length, width = rectangle_dimensions_from_area(
                config.ship.area_m2,
                config.ship.length_width_ratio,
            )

            platform = config.battery.platform
            shell = config.battery.shell
            header = (
                f"Platform: {platform.name}\n"
                f"Ship: {config.ship.name}\n"
                f"Battery size: {config.battery.gun_count}\n"
                f"Engagement range: "
                f"{config.battery.engagement_range_m:g}m\n"
                f"Interpolated spread radius: "
                f"{config.battery.gun.spread_radius_m:.2f}m\n"
                f"Firing cycle: "
                f"{platform.firing_time_s:g}s + "
                f"{platform.reload_time_s:g}s = "
                f"{platform.cycle_time_s:g}s\n"
                f"Shell: {shell.name}; base damage "
                f"{shell.base_damage:g}; effective damage "
                f"{shell.effective_damage:g} after "
                f"{self.ship_resistance * 100:.1f}% resistance\n"
                f"Total simulations: {total_runs}\n"
                f"Ship rectangle approximation: "
                f"{length:.1f}m x {width:.1f}m = "
                f"{config.ship.area_m2:.1f}m²\n"
                f"Damage chance per shell: "
                f"{p_damage * 100:.2f}%\n"
                f"Wet-hole chance per shell: "
                f"{p_hole * 100:.2f}%\n"
                f"Power bucketers offset: "
                f"{config.power_bucketers} holes worth of flow\n"
                f"HP retreat threshold: "
                f"{config.retreat.hp_retreat_fraction * 100:.1f}% "
                f"HP remaining\n"
            )

            self.summary_label.config(
                text=(
                    f"Ran {total_runs} simulations with "
                    f"{platform.name} "
                    f"({config.batch_size_per_threshold} per "
                    f"hole threshold)."
                )
            )
            self.output.delete("1.0", tk.END)
            self.output.insert(
                tk.END,
                header
                + "\n"
                + format_summary_table(summaries),
            )

        except Exception as error:
            messagebox.showerror(
                "Simulation error", str(error)
            )
