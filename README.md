# Artillery vs Ship Simulator v5

Run the application with:

```bash
python run_simulator_v5.py
```

Keep `artillery_data_v5.json`, `run_simulator_v5.py`, and the `artillery_simulator` folder together.


## Known issues
- Does not attempt to simulate dry holes becoming wet holes. Shells landing on the deck are incapable of making holes within this simulation
- High batch sizes can cause some lag while running
- Ships are simulated as rectangles - can lead to some innacurate results
- Only the Conqueror is available - I have no data on other ships flooding-wise and cannot simulate them accurately
- This does not simulate a DCL's decision to close bulwarks; the ship is considered to be a single floodable zone

## To-Do
- Add active firing of by the ship on counter-battery; this will be used to estimate a battery's lifetime while under fire
- Add ship v ship simulations; likely broadside only
- gather data on other ships during next devbranch if possible


