# PumpAhead -- CLAUDE.md

## Project Overview

PumpAhead is a predictive heating/cooling controller for Home Assistant (HACS custom integration). It uses Model Predictive Control (MPC) with RC thermal models to manage underfloor heating (UFH) and optional split/AC units.

**Status:** Pre-implementation. Algorithm spec complete, GitHub issues created (20 epics, 49 tasks). No code written yet.

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

## Architecture

```
pumpahead/              # Core library, zero HA dependency
  model.py              # 2R2C/3R3C RC state-space
  simulator.py          # Building digital twin
  optimizer.py          # MPC (cvxpy + OSQP)
  estimator.py          # Kalman filter
  controller.py         # PID with anti-windup
  identifier.py         # RC parameter identification (scipy)
  weather.py            # SyntheticWeather, CSVWeather, OpenMeteoHistorical
  scenarios.py          # RoomConfig, SimScenario, building profiles, scenario library
  metrics.py            # SimMetrics, assertion functions
  visualization.py      # matplotlib static plots, Plotly Dash replay

custom_components/pumpahead/   # HA integration, imports from pumpahead/
  manifest.json
  __init__.py
  climate.py            # ClimateEntity per room
  coordinator.py        # DataUpdateCoordinator (5 min)
  sensor.py             # Shadow mode diagnostics
  config_flow.py        # Entity mapping UI

tests/
  unit/                 # Fast: model, optimizer, identifier
  simulation/           # Slow: scenario-based (cold_snap, full_year, etc.)
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

- 20 epics (label: `epic`) -- #1 through #20
- 49 tasks (label: `task`) -- #21 through #69
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
