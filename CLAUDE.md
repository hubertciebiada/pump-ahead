# PumpAhead -- CLAUDE.md

## Project Overview

PumpAhead is a predictive heating/cooling controller for Home Assistant (HACS custom integration). It uses Model Predictive Control (MPC) with RC thermal models to manage underfloor heating (UFH) and optional split/AC units.

**Status:** Active development. M0–M7 complete, M8–M10 in progress. Core library mature (~15k LOC, ~2100 tests, 34 modules). HA integration scaffolded (config flow, coordinator, climate/sensor entities). Remaining work tracked via GitHub issues toward HACS release.

**Spec:** `PumpAhead_Algorithm_Spec.md` -- full mathematical and architectural specification.

## 10 Axioms (non-negotiable)

Every design decision must satisfy all ten. If a proposed solution violates any axiom, it is wrong.

1. **UFH is always primary.** UFH will always reach setpoint. Splits shorten the wait for comfort, they do not rescue UFH.
2. **Zero priority inversion.** Split > 30 min/h triggers forced UFH valve increase. Split never becomes primary.
3. **Splits never oppose the mode.** Heating: split never cools. Cooling: split never heats. Wait.
4. **T_floor <= 34 C hard limit.** Override valve immediately. (NOT 29 C from EN 1264 -- that's for normal conditions; at -15 C outdoor, 34 C floor is acceptable.)
5. **T_floor >= T_dew + 2 C.** Condensation protection. Immediate valve close on violation.
6. **Safety independent of algorithm.** HA YAML automations. Python crash cannot disable safety. Priority: Safety YAML > PumpAhead > HP curve.
7. **Thermal mass = battery.** C_slab ~ 3250 kJ/K ~ 10 kWh storage. Charge before frost, discharge before sun. C_slab/C_air ~ 54:1.
8. **Hardware-agnostic.** User maps HA entities. Unit validation only (C, %, W). No brand-specific code.
9. **Comfort > cost.** Tariff optimization is a soft objective. Comfort is a hard constraint. T_room < T_min is never acceptable for cost savings.
10. **Prediction >= 24h.** Slab tau = 4-6h. Reactive control loses to physics. MPC horizon must cover at least one full slab time constant.

## Production HA Server -- HANDS OFF

**ABSOLUTELY FORBIDDEN: Do NOT install, deploy, run, or modify anything on the user's Home Assistant server.** This is a PRODUCTION server running real hardware. Violating this rule can cause physical damage to the heating system or leave the house without heat.

| Action | Allowed? |
|--------|----------|
| Reading HA entity states, checking what HeishaMon exposes, querying sensor values | YES |
| Installing PumpAhead integration on HA | **NO** |
| Modifying HA configuration, automations, scripts, or entities | **NO** |
| Running any HA service call that changes state (e.g., `climate.set_temperature`, `switch.turn_on`) | **NO** |
| Making "temporary" or "testing" changes on HA | **NO** |

This restriction remains in effect until an explicit deployment task is created in the GitHub project and approved by the user. Until then, all development and testing happens locally in simulation only.

## Architecture

```
pumpahead/              # Core library, zero HA dependency (~15k LOC)
  # Modeling & simulation
  model.py              # 2R2C/3R3C RC state-space
  simulator.py          # Building digital twin (BuildingSimulator)
  simulated_room.py     # Per-room RK4 integration helper
  disturbance_vector.py # Discrete disturbance vector for MPC
  sensor_noise.py       # Gaussian noise for realism
  # Control
  controller.py         # PIDController + PumpAheadController
  optimizer.py          # MPC (cvxpy + OSQP)
  estimator.py          # Kalman filter
  identifier.py         # RC parameter identification (scipy)
  cross_validation.py   # RC parameter cross-validation
  identification_report.py  # IdentificationResult + reporting
  mode_controller.py    # Heating/cooling/auto state machine
  hp_mode_mapping.py    # HPOperatingState, SplitMode enum mappers
  # Hydraulics & physics
  ufh_loop.py           # EN 1264 reduced formula (loop_power, LoopGeometry)
  weather_comp.py       # Heating/cooling weather-compensation curves
  dew_point.py          # Magnus approximation, condensation protection
  solar.py              # Orientation-based Q_sol scaling
  solar_gti.py          # Full GTI with Erbs/Liu-Jordan decomposition
  # Weather, scenarios, metrics
  weather.py            # SyntheticWeather, CSVWeather, OpenMeteoHistorical
  scenarios.py          # RoomConfig, SimScenario, scenario library
  building_profiles.py  # Building profile builders (modern_bungalow, etc.)
  config.py             # Immutable configs (CWUCycle, BuildingParams, ControllerConfig)
  metrics.py            # SimMetrics + assertion functions
  cop_calculator.py     # COP baseline calculator
  # Coordination & safety
  split_coordinator.py  # Axiom 2/3: anti-takeover + mode-opposition guard
  cwu_coordinator.py    # DHW pre-charge + anti-panic (M6)
  safety_rules.py       # S1–S5 with hysteresis (Axiom 6)
  safety_yaml_generator.py  # Generates HA safety YAML from config
  watchdog.py           # S5 watchdog timeout
  # Logging, replay, A/B
  simulation_log.py     # Event data for replay
  log_serializer.py     # JSON serializer for logs
  visualization.py      # matplotlib static plots, Plotly Dash replay
  ab_testing.py         # ABTestRunner (PID vs MPC)
  # TODO (M9 — not yet implemented)
  # tariff.py           # G14 spot price client

custom_components/pumpahead/   # HA integration, imports from pumpahead/
  manifest.json
  __init__.py
  climate.py            # ClimateEntity per room
  coordinator.py        # DataUpdateCoordinator (5 min)
  sensor.py             # Shadow mode diagnostics
  config_flow.py        # Entity mapping UI (5-step wizard + options flow)
  const.py              # Domain, config keys, defaults
  entity_validator.py   # Unit validation (°C, %, W)
  ha_weather.py         # HA weather integration + solar ephemeris
  strings.json          # Default UI strings
  translations/         # en.json, pl.json
  brand/                # icon.svg (PNG conversion pending — see issue #169)

# Repo root
hacs.json               # HACS integration manifest
.github/workflows/validate.yml  # HACS + hassfest CI validation

tests/
  unit/                 # Fast: model, optimizer, identifier (~2000 tests)
  simulation/           # Slow: scenario-based (cold_snap, full_year, cooling, etc.)
```

**Key rule:** `pumpahead/` must NEVER import `homeassistant`. Core is testable standalone.

## Tech Stack

- Python 3.12+
- numpy, scipy -- RC model, identification
- cvxpy + OSQP -- QP solver for MPC
- matplotlib -- static plots
- plotly dash -- interactive simulation replay
- pytest -- testing (unit + simulation)
- ruff -- linting
- mypy -- type checking

## Mathematical Model

3R3C state-space: x = [T_air, T_slab, T_wall], u = [Q_floor, Q_conv], d = [T_out, Q_sol, Q_int]

```
C_air  * dT_air/dt  = (T_slab - T_air)/R_sf + (T_wall - T_air)/R_wi + (T_out - T_air)/R_ve + Q_conv + Q_int + f_conv*Q_sol
C_slab * dT_slab/dt = (T_air - T_slab)/R_sf + (T_ground - T_slab)/R_ins + Q_floor
C_wall * dT_wall/dt = (T_air - T_wall)/R_wi + (T_out - T_wall)/R_wo + f_rad*Q_sol
```

UFH-only rooms: B matrix is 3x1 (SISO). UFH+split rooms: B matrix is 3x2 (MIMO).

MPC cost function: J = sum[w_comfort*(T_room - T_set)^2 + c_elec*P_elec*dt + w_du*||du||^2]

## Milestone Roadmap

M0: RC model + simulator (pure Python, no HA) -- FOUNDATION
M1: PID controller for UFH
M2: HA integration read-only (shadow mode)
M3: RC parameter identification from data
M4: Live UFH control (one room, then scale)
M5: Split coordination (dual-source)
M6: DHW/CWU coordination
M7: MPC optimizer (cvxpy + OSQP) -- biggest quality leap
M8: Cooling mode + dew point protection
M9: Dynamic tariffs (G14 spot pricing)
M10: HACS release

Linear dependency chain. Each milestone builds on the previous one.

## GitHub Issues

- Epics labeled `epic`: #1–#20 plus ongoing quality/UFH epics (#137, #139)
- Tasks labeled `task`: implementation sub-issues under each epic
- Several new HACS-release tasks (#161–#171) under Epic #20
- Two relationship systems:
  - `parent/subIssues` -- epic is parent of its tasks
  - `blockedBy/blocking` -- dependency tracking between issues
- Query with GraphQL fields: `subIssues`, `blockedBy`, `blocking`, `parent`
- Do NOT use legacy `trackedIssues`/`trackedInIssues` fields

## Conventions

- Language: Python, PEP 8, type hints everywhere
- Testing: pytest, markers `@pytest.mark.unit`, `@pytest.mark.simulation`
- Scenario tests use `assert_comfort()`, `assert_no_priority_inversion()`, `assert_floor_temp_safe()` from metrics.py
- All temperatures in Celsius, all powers in Watts, all times in minutes (simulation) or seconds (real-time)
- Valve position: 0-100% float
- RC parameters: R in K/W, C in J/K (not kJ/K in code, only in docs)

## What NOT to Do

- Do not hardcode HeishaMon, Aquarea, VdMot, Mitsubishi, CN105 or any brand-specific entity IDs
- Do not use EN 1264 29 C floor limit -- our hard limit is 34 C
- Do not let splits work against the current mode (no cooling in heating mode, no heating in cooling mode)
- Do not optimize cost at the expense of comfort
- Do not import homeassistant in the pumpahead/ core library
- Do not use `trackedIssues`/`trackedInIssues` GraphQL fields -- use `subIssues`/`blockedBy`
