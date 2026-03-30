# PumpAhead

**Predictive heating and cooling control for Home Assistant -- turn your concrete slab into a thermal battery.**

[![HACS][hacs-badge]][hacs-url]
[![Home Assistant][ha-badge]][ha-url]
[![License][license-badge]][license-url]
[![Tests][tests-badge]][tests-url]

[hacs-badge]: https://img.shields.io/badge/HACS-Default-41BDF5.svg
[hacs-url]: https://hacs.xyz
[ha-badge]: https://img.shields.io/badge/Home%20Assistant-2024.1+-blue.svg
[ha-url]: https://www.home-assistant.io
[license-badge]: https://img.shields.io/github/license/hubertciebiada/pump-ahead
[license-url]: https://github.com/hubertciebiada/pump-ahead/blob/master/LICENSE
[tests-badge]: https://img.shields.io/badge/tests-passing-brightgreen
[tests-url]: https://github.com/hubertciebiada/pump-ahead/actions

---

## What PumpAhead Does

Most heat pump controllers are reactive -- they measure the current temperature and adjust output. With underfloor heating (UFH), that approach fails. A concrete slab has a thermal time constant of 4-6 hours: by the time the controller notices it is cold, it takes half a day to recover. The result is uncomfortable temperature swings and wasted energy.

PumpAhead replaces reactive control with **Model Predictive Control (MPC)**. It builds a mathematical thermal model (RC network) of each room, combines it with weather forecasts and energy price signals, and optimizes heating/cooling decisions 24 hours into the future. The 60-80 mm concrete slab under your floor becomes a thermal battery -- charged during cheap hours, discharged during expensive ones, pre-heated before cold fronts, and kept cool before sunny afternoons.

For rooms equipped with both underfloor heating and a split/AC unit, PumpAhead coordinates both sources. The slow, efficient UFH always handles the base load and will always reach the setpoint -- but with a time constant of hours, it may be too slow for sudden changes. The fast split **shortens the wait for comfort** when the model predicts UFH alone cannot reach the setpoint in time. A dedicated anti-takeover mechanism prevents the common pathology where the split inadvertently becomes the primary heat source (priority inversion).

---

## Design Principles

PumpAhead is built on ten non-negotiable axioms:

1. **UFH is always primary.** The underfloor heating will always reach the setpoint. The question is how fast. Splits shorten the wait, they do not rescue UFH.
2. **Zero priority inversion.** If a split runs more than 30 min/h, the system forces UFH valve increase. The split never becomes the de facto primary source.
3. **Splits never oppose the current mode.** In heating mode, the split never cools -- even on overshoot. In cooling mode, it never heats -- even on undershoot. Wait.
4. **T_floor <= 34 C is a hard limit.** At extreme outdoor temperatures (-15 C), higher floor temperatures are physically necessary and acceptable. Hard override on the valve.
5. **T_floor >= T_dew + 2 C -- condensation protection.** The only case where humidity is a critical measurement. Violation = immediate valve close.
6. **Safety runs independently of the algorithm.** YAML automations in HA. Python can crash -- safety cannot. Priority: Safety YAML > PumpAhead > HP built-in curve.
7. **Thermal mass is a battery, not a problem.** 3250 kJ/K of slab is ~10 kWh of storage. Charge before frost, discharge before sun. C_slab/C_air ~ 54:1 defines the entire system.
8. **Hardware-agnostic.** Users map HA entities at setup. Degrees C is degrees C, % is %, W is W. As long as the unit matches, the brand does not matter.
9. **Comfort always beats cost.** Tariff optimization cannot cause T_room to drop below T_min. The slab is a cheap battery, but comfort is a hard constraint, price is soft.
10. **Prediction horizon >= 24 hours.** The slab time constant is 4-6 hours. Reactive PID loses to physics. The only way is to look ahead -- weather, tariff, DHW.

---

## Key Features

- **Predictive control (MPC)** -- 24-hour rolling optimization horizon, 15-minute resolution, solving a small quadratic program in under 10 ms
- **Works with ANY heat pump, ANY valve actuators, ANY split/AC units** -- hardware-agnostic design; you map Home Assistant entities to roles during setup
- **Dual-source coordination** -- underfloor heating (primary) + split/AC (comfort boost), with deadband, anti-takeover logic, and priority inversion prevention
- **Floor cooling with dew point protection** -- automatic condensation prevention using room humidity sensors, enforcing T_floor >= T_dew + 2 C at all times
- **Auto-learning thermal model** -- RC parameter identification from your house's own data; the model improves over time with periodic re-fitting
- **Weather forecast integration** -- pre-heating before cold snaps, solar overshoot prevention for south-facing rooms, using Open-Meteo 48-hour forecasts
- **Dynamic tariff optimization** -- spot price integration (Polish G14 tariff, Nordpool, ENTSO-E); uses thermal mass as a cost-free energy buffer to shift consumption to cheap hours
- **DHW coordination** -- knows when the heat pump switches to domestic hot water, pre-charges the slab beforehand, and does not trigger unnecessary split activations during DHW cycles
- **Independent safety layer** -- YAML automations running outside the Python process; floor overheat protection (34 C hard limit), dew point override, emergency fallback, watchdog with HP curve fallback
- **Built-in building simulator** -- full digital twin for offline testing; a year-long simulation runs in under a minute
- **Interactive simulation replay** -- Plotly Dash application with synchronized timelines, playback controls, and per-room gauges

---

## How It Works

### The RC Thermal Model

Each room is modeled as an electrical RC circuit -- an analogy where temperature corresponds to voltage, heat flow to current, thermal resistance (walls, windows, insulation) to electrical resistance, and thermal mass (concrete slab, air, walls) to capacitance. PumpAhead uses a 3R3C model with three state variables per room:

| Node | Physical meaning | Time constant |
|------|-----------------|---------------|
| T_air | Room air temperature | Minutes (fast) |
| T_slab | Concrete slab temperature | 4-6 hours (slow) |
| T_wall | Building envelope temperature | Hours to days |

The ratio C_slab / C_air is approximately 54:1 -- the slab stores 54 times more energy than the air. This massive thermal inertia is both the challenge (slow response) and the opportunity (free energy storage).

### MPC Optimization

Every 5-15 minutes, PumpAhead:

1. Reads sensor data from Home Assistant (room temperatures, humidity, outdoor temperature, heat pump state)
2. Updates a Kalman filter to estimate the full state vector (including unmeasured slab and wall temperatures)
3. Fetches a 48-hour weather forecast (temperature, solar irradiance, humidity)
4. Solves a quadratic program minimizing a cost function that balances thermal comfort, energy cost, and actuator wear over a 24-hour horizon (96 time steps)
5. Applies only the first control step (valve positions, split on/off), then repeats

This receding-horizon approach naturally handles forecast errors and changing conditions.

### Phased Rollout

PumpAhead is designed for cautious deployment:

1. **Shadow mode** -- the integration reads sensors and logs what it would do, but controls nothing. Compare its recommendations against your current system for as long as you need.
2. **Single room** -- enable control for one room and observe for a week.
3. **Full house** -- roll out room by room once confidence is established.

---

## Supported Hardware

PumpAhead is hardware-agnostic. It works with any equipment that exposes Home Assistant entities. During setup, you map entities to roles (temperature sensor, valve position, heat pump mode, etc.). As long as the unit of measurement is correct, the brand does not matter.

### Example Setups

| Component | Example 1 | Example 2 | Example 3 |
|-----------|-----------|-----------|-----------|
| Heat pump | Panasonic Aquarea + HeishaMon | Daikin Altherma (native HA) | Vaillant aroTHERM + eBUS |
| Valve controller | VdMot (MQTT) | Salus iT600 (WiFi) | Homematic IP (CCU3) |
| Split/AC | Mitsubishi via ESPHome (CN105) | Daikin WiFi adapter | Any `climate` entity |
| Temp sensors | Aqara Zigbee | Shelly H&T Gen3 | Sonoff SNZB-02 |
| Power meter | Shelly EM | Tuya smart plug | Built-in HP metering |

### Required Entities

| Role | Type | Notes |
|------|------|-------|
| Room temperature (per room) | `sensor` (C) | At least one per controlled room |
| Outdoor temperature | `sensor` (C) | From HP, weather station, or HA weather integration |
| Supply water temperature | `sensor` (C) | From HP integration |
| Valve position (per room) | `number` (0-100%) | Any controllable valve actuator |
| Heat pump operating mode | `sensor` | States mapped to: heating / DHW / idle / defrost / cooling |

### Optional Entities

| Role | Type | When needed |
|------|------|-------------|
| Room humidity (per room) | `sensor` (%) | Required for cooling mode (dew point protection) |
| Floor surface temperature | `sensor` (C) | Improves slab temperature estimation |
| Split/AC (per room) | `climate` entity | Rooms with dual-source control |
| HP electrical power | `sensor` (W) | COP calculation, tariff optimization |
| Return water temperature | `sensor` (C) | Better COP calculation |
| DHW tank temperature | `sensor` (C) | DHW cycle planning |

---

## Installation

### Via HACS (recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations** and click the three-dot menu
3. Select **Custom repositories** and add: `https://github.com/hubertciebiada/pump-ahead`
4. Search for **PumpAhead** and install
5. Restart Home Assistant
6. Go to **Settings > Devices & Services > Add Integration** and search for **PumpAhead**

### Manual Installation

1. Download the latest release from GitHub
2. Copy `custom_components/pumpahead/` to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant
4. Add the integration through the UI

---

## Configuration

PumpAhead is configured entirely through the Home Assistant UI -- no YAML editing required.

### Setup Steps

1. **Global entities** -- Map your heat pump's entities: outdoor temperature, supply temperature, operating mode. Map the operating mode states to PumpAhead's internal states (heating/cooling/DHW/idle/defrost). Optionally: return temperature, power consumption, DHW tank temperature.

2. **Add rooms** -- For each room, provide:
   - Room name and floor area
   - Temperature sensor entity
   - Valve actuator entity
   - Window orientation(s) and area (for solar gain prediction)
   - Whether the room has a split/AC unit (and which `climate` entity)
   - Humidity sensor (required for cooling mode)

3. **Set parameters** -- Configure setpoints, deadband (default 0.5 C), valve floor minimum (default 15%), and heating/cooling mode.

4. **Start in shadow mode** -- PumpAhead begins by observing and logging recommendations without controlling anything. Run shadow mode for at least 2-4 weeks to collect data for thermal model identification.

5. **Enable control** -- Once the thermal model is identified and you trust the recommendations, enable live control one room at a time.

---

## Architecture

PumpAhead follows a strict separation between the core algorithm library and the Home Assistant integration layer.

```
pump-ahead/
|-- pumpahead/                          # Core library (no HA dependency)
|   |-- model.py                        # 2R2C / 3R3C RC state-space models
|   |-- simulator.py                    # Building digital twin
|   |-- optimizer.py                    # MPC (cvxpy + OSQP QP solver)
|   |-- estimator.py                    # Kalman filter for state estimation
|   |-- controller.py                   # PID controller with anti-windup
|   |-- identifier.py                   # RC parameter identification from data
|   |-- weather.py                      # Weather sources (synthetic, CSV, Open-Meteo)
|   |-- scenarios.py                    # Simulation scenarios and building profiles
|   |-- metrics.py                      # Simulation metrics and assertions
|   +-- visualization.py               # matplotlib plots, Plotly Dash replay app
|
|-- custom_components/pumpahead/        # HA integration (imports from pumpahead core)
|   |-- manifest.json
|   |-- __init__.py                     # Entry point, coordinator setup
|   |-- climate.py                      # ClimateEntity per room
|   |-- coordinator.py                  # DataUpdateCoordinator (5-min cycle)
|   |-- sensor.py                       # Diagnostic sensors (shadow mode)
|   |-- config_flow.py                  # UI configuration with entity mapping
|   +-- translations/                   # EN, PL
|
+-- tests/
    |-- unit/                           # Fast tests (<1s): model, optimizer, identifier
    +-- simulation/                     # Scenario tests: steady-state, cold snap, full year
```

The core library depends only on numpy, scipy, cvxpy, and matplotlib. It can be used standalone in Jupyter notebooks for offline analysis, parameter identification, and simulation without Home Assistant.

---

## For Developers

### Prerequisites

- Python 3.12+
- Dependencies managed via `pyproject.toml`

### Quick Start

```bash
git clone https://github.com/hubertciebiada/pump-ahead.git
cd pump-ahead
pip install -e ".[dev]"
```

### Running Tests

```bash
# All tests
pytest

# Unit tests only (fast)
pytest tests/unit/

# Simulation scenarios (slower, includes full-year runs)
pytest tests/simulation/

# With coverage
pytest --cov=pumpahead --cov-report=html
```

### Code Quality

```bash
ruff check .
mypy pumpahead/
ruff format .
```

### Running the Simulator

```python
from pumpahead.simulator import BuildingSimulator
from pumpahead.scenarios import SCENARIOS
from pumpahead.controller import PumpAheadController

scenario = SCENARIOS["cold_snap"]
sim = BuildingSimulator(
    rooms=scenario.rooms,
    params=scenario.building_params,
    weather=scenario.weather_source,
)
ctrl = PumpAheadController(config=scenario.controller_config)

for t in range(scenario.duration_minutes):
    measurements = sim.get_measurements(noise=scenario.sensor_noise)
    actions = ctrl.step(measurements, t)
    sim.apply(actions)
```

### Interactive Replay

```bash
python -m pumpahead.replay
```

---

## FAQ

**Q: Do I need a specific brand of heat pump?**
A: No. PumpAhead works with any heat pump that has a Home Assistant integration. You map your HA entities to roles during setup. As long as the units match, the brand does not matter.

**Q: Does it work without split/AC units?**
A: Yes. Most rooms have only underfloor heating. PumpAhead works in UFH-only mode -- predictive pre-loading of the slab becomes even more important without a fast comfort source.

**Q: What happens if the internet goes down?**
A: PumpAhead falls back to the most recent forecast (if less than 6 hours old), then to the current outdoor temperature with zero solar gains. The system continues to function without anticipatory optimization.

**Q: What happens if PumpAhead crashes?**
A: The independent safety layer (YAML automations) continues regardless. A watchdog detects if PumpAhead stops responding and falls back to the heat pump's built-in curve. Floor overheat and condensation protections remain active at all times.

**Q: Is night setback recommended?**
A: No. With high thermal inertia systems, night setback is counterproductive. The energy saved overnight is offset by the energy needed to reheat the massive slab in the morning. PumpAhead maintains stable temperatures 24/7.

**Q: Can I use it for cooling?**
A: Yes. PumpAhead supports floor cooling with automatic dew point protection. A humidity sensor is required in each cooled room. The system enforces T_floor >= T_dew + 2 C at all times.

**Q: How long before the system is optimized for my house?**
A: Shadow mode collects data for 2-4 weeks. The thermal model learns each room's characteristics. After identification, you can enable live control.

---

## Academic Foundations

| Concept | Reference | Contribution |
|---------|-----------|-------------|
| MPC for radiant + convective systems | Drgona, Picard & Helsen (2020). *Journal of Process Control* | 53.5% energy savings, 36.9% comfort improvement vs rule-based |
| Stochastic MPC with weather forecasts | Oldewurtel et al. (2012). *Energy and Buildings* | Imperfect forecasts still outperform no forecast for high-inertia systems |
| RC model for pipe-embedded floors | Liu et al. (2016). *Energy and Buildings* | Star-type RC model, <5.5% error vs FEM |
| MPC for radiant floor optimization | Li et al. (2021). *Energy* | 56% faster response, +24.5% COP vs PID |
| Hierarchical MIMO MPC | Killian & Kozek (2018). *Applied Energy* | Two-level MPC for slow building dynamics + fast component switching |
| 2nd-order model sufficiency | Sourbron & Verhelst (2013) | 2R2C sufficient for MPC; higher-order models do not proportionally improve control |
| Singular perturbation decomposition | Gupta et al. (2017) | C_air/C_slab << 1 enables slow/fast subsystem decomposition |
| Priority inversion in radiant systems | Tekmar Essay E006 (Watts) | PWM on slow source prevents fast source takeover |
| hybridGEOTABS | EU Horizon 2020, KU Leuven / EnergyVille | Supervisory MPC + local PI in 32-zone building |

---

## License

This project is licensed under the [GNU Affero General Public License v3.0](LICENSE).
