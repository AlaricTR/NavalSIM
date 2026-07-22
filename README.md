# Artillery vs Ship Simulator v6

Run from this folder with:

```bash
python run_simulator_v6.py
```

Keep `artillery_data_v6.json`, `run_simulator_v6.py`, and the `artillery_simulator` folder together.

## Version 6 changes

- Adds an optional **Ship fires at battery (duel)** checkbox.
- The duel is not simulated when the checkbox is clear.
- Enabling the checkbox adds a **Duel Results** tab.
- Guns have independent HP and stop firing when destroyed.
- A battery is dead only when every gun reaches 0 HP.
- Batteries are modeled as straight-line formations.
- Koronides uses 3.25 m center spacing, 1,000 HP, 70% resistance, and exposed pushgun blast-radius vulnerability.
- Entrenched guns use 9 m center spacing and a 4 m trench vulnerability radius.
- Ship turrets use a hardcoded 2.5–8.5 m spread curve over 100–200 m, clamped outside that range.
- When the best target group changes because the entire living battery does not fit inside the current spread, naval retargeting takes a random 5–10 seconds.
- Engagements above 250 m display a warning but still run.

## Result tabs

**Ship Results** shows the existing ship survival, HP, flooding, wet-hole, and battery-fire statistics. In duel mode these results account for guns being destroyed and ceasing fire.

**Duel Results** shows, for every tested wet-hole retreat threshold:

- percentage of trials where the battery forced retreat;
- percentage where the battery was destroyed first;
- ship-destruction, simultaneous, and timeout percentages;
- average and median battery time in the fight;
- average battery destruction time for trials where it died;
- average guns destroyed/remaining, battery HP, naval shells, impacts, and retargets.

The HP retreat threshold is fixed by the GUI field and is printed above the duel table. Each table row varies the wet-hole threshold.

## Module layout

- `models.py` — immutable definitions, configs, and result objects
- `data_loader.py` — JSON discovery, parsing, and validation
- `geometry.py` — ship hit probability and linear-battery naval targeting
- `ship_state.py` — shared HP, flooding, leak, and repair state
- `simulation.py` — battery-only Monte Carlo simulation
- `duel_simulation.py` — mutual ship-versus-battery simulation
- `formatting.py` — result table and time formatting
- `tooltip.py` — reusable hover tooltips
- `gui.py` — form, tabs, warnings, validation, and run handling
- `run_simulator_v6.py` — minimal launcher
