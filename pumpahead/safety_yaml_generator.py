"""YAML automation generator for Home Assistant safety rules S1-S5.

Produces valid Home Assistant automation YAML from PumpAhead
configuration.  Each safety rule (S1 floor overheat, S2 condensation,
S3 emergency heat, S4 emergency cool, S5 watchdog) generates a
trigger/clear automation pair with hysteresis.

The generator uses plain Python dicts serialised via ``yaml.safe_dump``
-- no Jinja2 template engine, no ``homeassistant`` imports.  The HA
integration calls this generator; the generator itself is pure Python.

Entity IDs are injected from a ``RoomEntityConfig`` dataclass that
mirrors the config flow entity mapping keys.

Design principles:
    * Zero ``homeassistant`` dependency (Axiom #8 / CLAUDE.md rule).
    * Output is round-trip safe: ``yaml.safe_load(output)`` always
      succeeds and produces the same dicts.
    * Hysteresis expressed via separate trigger/clear automations using
      ``numeric_state`` triggers with ``above``/``below``.
    * S2 (condensation) and S5 (watchdog) use ``template`` triggers
      because their thresholds are computed at runtime.

Units:
    Temperatures: degC
    Humidity: % (0-100)
    Time: minutes (for watchdog)
"""

from __future__ import annotations

from dataclasses import dataclass

import yaml

from pumpahead.safety_rules import (
    S1_FLOOR_OVERHEAT,
    S2_CONDENSATION,
    S3_EMERGENCY_HEAT,
    S4_EMERGENCY_COOL,
    S5_WATCHDOG,
)

# ---------------------------------------------------------------------------
# Configuration dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoomEntityConfig:
    """Entity mapping for a single room.

    Maps PumpAhead concepts to Home Assistant entity IDs.  The
    ``entity_split`` field is optional -- rooms without a split/AC
    unit omit it.

    Attributes:
        room_name: Human-readable room name (used in automation IDs
            and descriptions).
        entity_temp_floor: HA entity for floor temperature sensor.
        entity_temp_room: HA entity for room air temperature sensor.
        entity_humidity: HA entity for room humidity sensor.
        entity_valve: HA entity for UFH valve (number or input_number).
        entity_split: HA entity for split/AC climate entity, or
            ``None`` if the room has no split.
    """

    room_name: str
    entity_temp_floor: str
    entity_temp_room: str
    entity_humidity: str
    entity_valve: str
    entity_split: str | None = None

    def __post_init__(self) -> None:
        if not self.room_name or not self.room_name.strip():
            msg = "room_name must be non-empty"
            raise ValueError(msg)
        if not self.entity_temp_floor or not self.entity_temp_floor.strip():
            msg = "entity_temp_floor must be non-empty"
            raise ValueError(msg)
        if not self.entity_temp_room or not self.entity_temp_room.strip():
            msg = "entity_temp_room must be non-empty"
            raise ValueError(msg)
        if not self.entity_humidity or not self.entity_humidity.strip():
            msg = "entity_humidity must be non-empty"
            raise ValueError(msg)
        if not self.entity_valve or not self.entity_valve.strip():
            msg = "entity_valve must be non-empty"
            raise ValueError(msg)


@dataclass(frozen=True)
class SafetyYAMLConfig:
    """Global configuration for safety YAML generation.

    Holds per-room entity mappings plus optional threshold overrides.
    Default thresholds come from the ``safety_rules.py`` constants.

    Attributes:
        rooms: Per-room entity configurations.  Room names must be
            unique.
        entity_pumpahead_last_update: HA entity for PumpAhead last
            update timestamp sensor (used by S5 watchdog).
        s1_threshold_on: S1 trigger temperature [degC].
        s1_threshold_off: S1 clear temperature [degC].
        s2_condensation_margin: S2 condensation margin [degC].  The
            dew point safety margin (T_floor >= T_dew + margin).
        s2_threshold_off_margin: S2 clear margin above the
            condensation threshold [degC].
        s3_threshold_on: S3 emergency heat trigger [degC].
        s3_threshold_off: S3 emergency heat clear [degC].
        s4_threshold_on: S4 emergency cool trigger [degC].
        s4_threshold_off: S4 emergency cool clear [degC].
        s5_threshold_on: S5 watchdog trigger [minutes].
        s5_threshold_off: S5 watchdog clear [minutes].
        entity_hp_thermostat: HA entity for the heat pump's native
            thermostat (e.g., ``climate.heat_pump``).  When set,
            the S5 fallback action restores native HP control.
            ``None`` means no HP thermostat action (Axiom #8).
        entity_watchdog_flag: HA ``input_boolean`` entity that
            tracks whether watchdog fallback is active.  Defaults
            to ``input_boolean.pumpahead_watchdog_fallback``.
    """

    rooms: tuple[RoomEntityConfig, ...]
    entity_pumpahead_last_update: str = "sensor.pumpahead_last_update"

    # S1: Floor overheat
    s1_threshold_on: float = S1_FLOOR_OVERHEAT.threshold_on
    s1_threshold_off: float = S1_FLOOR_OVERHEAT.threshold_off

    # S2: Condensation -- margin is the +2 in T_floor >= T_dew + 2
    s2_condensation_margin: float = 2.0
    s2_threshold_off_margin: float = S2_CONDENSATION.threshold_off

    # S3: Emergency heat
    s3_threshold_on: float = S3_EMERGENCY_HEAT.threshold_on
    s3_threshold_off: float = S3_EMERGENCY_HEAT.threshold_off

    # S4: Emergency cool
    s4_threshold_on: float = S4_EMERGENCY_COOL.threshold_on
    s4_threshold_off: float = S4_EMERGENCY_COOL.threshold_off

    # S5: Watchdog
    s5_threshold_on: float = S5_WATCHDOG.threshold_on
    s5_threshold_off: float = S5_WATCHDOG.threshold_off

    # Watchdog fallback entities
    entity_hp_thermostat: str | None = None
    entity_watchdog_flag: str = "input_boolean.pumpahead_watchdog_fallback"

    def __post_init__(self) -> None:
        if not self.rooms:
            msg = "rooms must be non-empty"
            raise ValueError(msg)
        names = [r.room_name for r in self.rooms]
        if len(names) != len(set(names)):
            msg = f"room names must be unique, got duplicates in {names}"
            raise ValueError(msg)
        if not self.entity_pumpahead_last_update.strip():
            msg = "entity_pumpahead_last_update must be non-empty"
            raise ValueError(msg)
        # Validate threshold relationships
        if self.s1_threshold_off > self.s1_threshold_on:
            msg = (
                f"S1: threshold_off ({self.s1_threshold_off}) must be "
                f"<= threshold_on ({self.s1_threshold_on})"
            )
            raise ValueError(msg)
        if self.s3_threshold_off < self.s3_threshold_on:
            msg = (
                f"S3: threshold_off ({self.s3_threshold_off}) must be "
                f">= threshold_on ({self.s3_threshold_on})"
            )
            raise ValueError(msg)
        if self.s4_threshold_off > self.s4_threshold_on:
            msg = (
                f"S4: threshold_off ({self.s4_threshold_off}) must be "
                f"<= threshold_on ({self.s4_threshold_on})"
            )
            raise ValueError(msg)
        if self.s5_threshold_off > self.s5_threshold_on:
            msg = (
                f"S5: threshold_off ({self.s5_threshold_off}) must be "
                f"<= threshold_on ({self.s5_threshold_on})"
            )
            raise ValueError(msg)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _slug(room_name: str) -> str:
    """Convert a room name to a slug for automation IDs.

    Lowercases, replaces spaces and special chars with underscores,
    strips leading/trailing underscores.

    >>> _slug("Living Room")
    'living_room'
    >>> _slug("Łazienka Górna")
    'lazienka_gorna'
    """
    import re
    import unicodedata

    # Normalise unicode (e.g., Polish characters) to ASCII
    nfkd = unicodedata.normalize("NFKD", room_name)
    ascii_name = nfkd.encode("ascii", "ignore").decode("ascii")
    # Replace non-alphanumeric with underscore
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_name.lower())
    return slug.strip("_")


# ---------------------------------------------------------------------------
# S1: Floor overheat protection
# ---------------------------------------------------------------------------


def _build_s1_automations(
    room: RoomEntityConfig,
    config: SafetyYAMLConfig,
) -> list[dict[str, object]]:
    """Build S1 floor overheat trigger + clear automations.

    S1 uses ``numeric_state`` triggers:
    - Trigger: T_floor > threshold_on -> close valve
    - Clear: T_floor < threshold_off -> (no valve change, just log)

    Args:
        room: Room entity configuration.
        config: Global safety YAML configuration.

    Returns:
        List of two automation dicts (trigger + clear).
    """
    slug = _slug(room.room_name)

    trigger_auto: dict[str, object] = {
        "id": f"pumpahead_s1_floor_overheat_trigger_{slug}",
        "alias": f"PumpAhead S1: Floor Overheat Trigger - {room.room_name}",
        "description": (
            f"Safety rule S1: Close UFH valve when floor temperature "
            f"exceeds {config.s1_threshold_on}C in {room.room_name}. "
            f"Axiom #4: T_floor <= 34C hard limit."
        ),
        "mode": "single",
        "trigger": [
            {
                "platform": "numeric_state",
                "entity_id": room.entity_temp_floor,
                "above": config.s1_threshold_on,
            },
        ],
        "condition": [],
        "action": [
            {
                "service": "number.set_value",
                "target": {"entity_id": room.entity_valve},
                "data": {"value": 0},
            },
            {
                "service": "persistent_notification.create",
                "data": {
                    "title": "PumpAhead Safety S1",
                    "message": (
                        f"Floor overheat in {room.room_name}: "
                        f"T_floor > {config.s1_threshold_on}C. "
                        f"Valve closed."
                    ),
                },
            },
        ],
    }

    clear_auto: dict[str, object] = {
        "id": f"pumpahead_s1_floor_overheat_clear_{slug}",
        "alias": f"PumpAhead S1: Floor Overheat Clear - {room.room_name}",
        "description": (
            f"Safety rule S1 clear: Floor temperature in {room.room_name} "
            f"dropped below {config.s1_threshold_off}C. "
            f"Normal operation can resume."
        ),
        "mode": "single",
        "trigger": [
            {
                "platform": "numeric_state",
                "entity_id": room.entity_temp_floor,
                "below": config.s1_threshold_off,
            },
        ],
        "condition": [],
        "action": [
            {
                "service": "persistent_notification.create",
                "data": {
                    "title": "PumpAhead Safety S1",
                    "message": (
                        f"Floor overheat cleared in {room.room_name}: "
                        f"T_floor < {config.s1_threshold_off}C. "
                        f"Normal operation can resume."
                    ),
                },
            },
        ],
    }

    return [trigger_auto, clear_auto]


# ---------------------------------------------------------------------------
# S2: Condensation protection
# ---------------------------------------------------------------------------


def _build_s2_automations(
    room: RoomEntityConfig,
    config: SafetyYAMLConfig,
) -> list[dict[str, object]]:
    """Build S2 condensation trigger + clear automations.

    S2 uses ``template`` triggers because the threshold is computed
    from room temperature and humidity (dew point + margin).

    The dew point formula uses the simplified Magnus approximation:
    ``T_dew = T_room - (100 - humidity) / 5``

    Trigger condition: T_floor < T_dew + margin (condensation risk)
    Clear condition: T_floor > T_dew + margin + clear_margin

    Args:
        room: Room entity configuration.
        config: Global safety YAML configuration.

    Returns:
        List of two automation dicts (trigger + clear).
    """
    slug = _slug(room.room_name)
    margin = config.s2_condensation_margin
    clear_margin = config.s2_threshold_off_margin

    # Jinja2 template for HA: compute dew point + margin and compare
    trigger_template = (
        f"{{% set t_floor = states('{room.entity_temp_floor}') | float(0) %}}\n"
        f"{{% set t_room = states('{room.entity_temp_room}') | float(0) %}}\n"
        f"{{% set rh = states('{room.entity_humidity}') | float(50) %}}\n"
        f"{{% set t_dew = t_room - (100 - rh) / 5 %}}\n"
        f"{{{{ t_floor < (t_dew + {margin}) }}}}"
    )

    clear_template = (
        f"{{% set t_floor = states('{room.entity_temp_floor}') | float(0) %}}\n"
        f"{{% set t_room = states('{room.entity_temp_room}') | float(0) %}}\n"
        f"{{% set rh = states('{room.entity_humidity}') | float(50) %}}\n"
        f"{{% set t_dew = t_room - (100 - rh) / 5 %}}\n"
        f"{{{{ t_floor > (t_dew + {margin} + {clear_margin}) }}}}"
    )

    trigger_auto: dict[str, object] = {
        "id": f"pumpahead_s2_condensation_trigger_{slug}",
        "alias": f"PumpAhead S2: Condensation Trigger - {room.room_name}",
        "description": (
            f"Safety rule S2: Close UFH valve when floor temperature "
            f"drops below dew point + {margin}C in {room.room_name}. "
            f"Axiom #5: T_floor >= T_dew + 2C."
        ),
        "mode": "single",
        "trigger": [
            {
                "platform": "template",
                "value_template": trigger_template,
            },
        ],
        "condition": [],
        "action": [
            {
                "service": "number.set_value",
                "target": {"entity_id": room.entity_valve},
                "data": {"value": 0},
            },
            {
                "service": "persistent_notification.create",
                "data": {
                    "title": "PumpAhead Safety S2",
                    "message": (
                        f"Condensation risk in {room.room_name}: "
                        f"T_floor < T_dew + {margin}C. "
                        f"Valve closed."
                    ),
                },
            },
        ],
    }

    clear_auto: dict[str, object] = {
        "id": f"pumpahead_s2_condensation_clear_{slug}",
        "alias": f"PumpAhead S2: Condensation Clear - {room.room_name}",
        "description": (
            f"Safety rule S2 clear: Condensation risk resolved in "
            f"{room.room_name}. T_floor > T_dew + "
            f"{margin + clear_margin}C."
        ),
        "mode": "single",
        "trigger": [
            {
                "platform": "template",
                "value_template": clear_template,
            },
        ],
        "condition": [],
        "action": [
            {
                "service": "persistent_notification.create",
                "data": {
                    "title": "PumpAhead Safety S2",
                    "message": (
                        f"Condensation risk cleared in {room.room_name}. "
                        f"Normal operation can resume."
                    ),
                },
            },
        ],
    }

    return [trigger_auto, clear_auto]


# ---------------------------------------------------------------------------
# S3: Emergency heating
# ---------------------------------------------------------------------------


def _build_s3_automations(
    room: RoomEntityConfig,
    config: SafetyYAMLConfig,
) -> list[dict[str, object]]:
    """Build S3 emergency heating trigger + clear automations.

    S3 uses ``numeric_state`` triggers:
    - Trigger: T_room < threshold_on -> valve 100% + split heat (if present)
    - Clear: T_room > threshold_off -> notification only

    Args:
        room: Room entity configuration.
        config: Global safety YAML configuration.

    Returns:
        List of two automation dicts (trigger + clear).
    """
    slug = _slug(room.room_name)

    # Build actions: always set valve to 100%
    trigger_actions: list[dict[str, object]] = [
        {
            "service": "number.set_value",
            "target": {"entity_id": room.entity_valve},
            "data": {"value": 100},
        },
    ]

    # If split exists, turn on heating
    if room.entity_split is not None:
        trigger_actions.append(
            {
                "service": "climate.set_hvac_mode",
                "target": {"entity_id": room.entity_split},
                "data": {"hvac_mode": "heat"},
            },
        )

    trigger_actions.append(
        {
            "service": "persistent_notification.create",
            "data": {
                "title": "PumpAhead Safety S3",
                "message": (
                    f"Emergency heating in {room.room_name}: "
                    f"T_room < {config.s3_threshold_on}C. "
                    f"Valve set to 100%"
                    + (", split set to heat." if room.entity_split is not None else ".")
                ),
            },
        },
    )

    trigger_auto: dict[str, object] = {
        "id": f"pumpahead_s3_emergency_heat_trigger_{slug}",
        "alias": f"PumpAhead S3: Emergency Heat Trigger - {room.room_name}",
        "description": (
            f"Safety rule S3: Emergency heating when room temperature "
            f"drops below {config.s3_threshold_on}C in {room.room_name}."
        ),
        "mode": "single",
        "trigger": [
            {
                "platform": "numeric_state",
                "entity_id": room.entity_temp_room,
                "below": config.s3_threshold_on,
            },
        ],
        "condition": [],
        "action": trigger_actions,
    }

    # Clear automation
    clear_actions: list[dict[str, object]] = [
        {
            "service": "persistent_notification.create",
            "data": {
                "title": "PumpAhead Safety S3",
                "message": (
                    f"Emergency heating cleared in {room.room_name}: "
                    f"T_room > {config.s3_threshold_off}C. "
                    f"Normal operation can resume."
                ),
            },
        },
    ]

    clear_auto: dict[str, object] = {
        "id": f"pumpahead_s3_emergency_heat_clear_{slug}",
        "alias": f"PumpAhead S3: Emergency Heat Clear - {room.room_name}",
        "description": (
            f"Safety rule S3 clear: Room temperature in {room.room_name} "
            f"recovered above {config.s3_threshold_off}C."
        ),
        "mode": "single",
        "trigger": [
            {
                "platform": "numeric_state",
                "entity_id": room.entity_temp_room,
                "above": config.s3_threshold_off,
            },
        ],
        "condition": [],
        "action": clear_actions,
    }

    return [trigger_auto, clear_auto]


# ---------------------------------------------------------------------------
# S4: Emergency cooling
# ---------------------------------------------------------------------------


def _build_s4_automations(
    room: RoomEntityConfig,
    config: SafetyYAMLConfig,
) -> list[dict[str, object]]:
    """Build S4 emergency cooling trigger + clear automations.

    S4 uses ``numeric_state`` triggers:
    - Trigger: T_room > threshold_on -> split cool (if present)
    - Clear: T_room < threshold_off -> notification only

    If the room has no split, no trigger automation actions can
    actuate cooling.  The valve-only action closes the valve to
    stop heating, plus notification.

    Args:
        room: Room entity configuration.
        config: Global safety YAML configuration.

    Returns:
        List of two automation dicts (trigger + clear).
    """
    slug = _slug(room.room_name)

    # Build actions
    trigger_actions: list[dict[str, object]] = []

    if room.entity_split is not None:
        trigger_actions.append(
            {
                "service": "climate.set_hvac_mode",
                "target": {"entity_id": room.entity_split},
                "data": {"hvac_mode": "cool"},
            },
        )

    # Also close valve to stop heating contribution
    trigger_actions.append(
        {
            "service": "number.set_value",
            "target": {"entity_id": room.entity_valve},
            "data": {"value": 0},
        },
    )

    trigger_actions.append(
        {
            "service": "persistent_notification.create",
            "data": {
                "title": "PumpAhead Safety S4",
                "message": (
                    f"Emergency cooling in {room.room_name}: "
                    f"T_room > {config.s4_threshold_on}C. "
                    + (
                        "Split set to cool, valve closed."
                        if room.entity_split is not None
                        else "Valve closed."
                    )
                ),
            },
        },
    )

    trigger_auto: dict[str, object] = {
        "id": f"pumpahead_s4_emergency_cool_trigger_{slug}",
        "alias": f"PumpAhead S4: Emergency Cool Trigger - {room.room_name}",
        "description": (
            f"Safety rule S4: Emergency cooling when room temperature "
            f"exceeds {config.s4_threshold_on}C in {room.room_name}."
        ),
        "mode": "single",
        "trigger": [
            {
                "platform": "numeric_state",
                "entity_id": room.entity_temp_room,
                "above": config.s4_threshold_on,
            },
        ],
        "condition": [],
        "action": trigger_actions,
    }

    # Clear automation
    clear_actions: list[dict[str, object]] = [
        {
            "service": "persistent_notification.create",
            "data": {
                "title": "PumpAhead Safety S4",
                "message": (
                    f"Emergency cooling cleared in {room.room_name}: "
                    f"T_room < {config.s4_threshold_off}C. "
                    f"Normal operation can resume."
                ),
            },
        },
    ]

    clear_auto: dict[str, object] = {
        "id": f"pumpahead_s4_emergency_cool_clear_{slug}",
        "alias": f"PumpAhead S4: Emergency Cool Clear - {room.room_name}",
        "description": (
            f"Safety rule S4 clear: Room temperature in {room.room_name} "
            f"dropped below {config.s4_threshold_off}C."
        ),
        "mode": "single",
        "trigger": [
            {
                "platform": "numeric_state",
                "entity_id": room.entity_temp_room,
                "below": config.s4_threshold_off,
            },
        ],
        "condition": [],
        "action": clear_actions,
    }

    return [trigger_auto, clear_auto]


# ---------------------------------------------------------------------------
# S5: Watchdog timeout
# ---------------------------------------------------------------------------


def _build_s5_trigger_actions(
    config: SafetyYAMLConfig,
) -> list[dict[str, object]]:
    """Build action list for the S5 watchdog trigger automation.

    Actions include:
    - Notification about watchdog timeout.
    - Turn on the watchdog fallback flag (``input_boolean``).
    - Optionally restore HP native control (if ``entity_hp_thermostat``
      is configured).

    Args:
        config: Global safety YAML configuration.

    Returns:
        List of HA action dicts.
    """
    actions: list[dict[str, object]] = [
        {
            "service": "persistent_notification.create",
            "data": {
                "title": "PumpAhead Safety S5",
                "message": (
                    f"PumpAhead watchdog: No update for "
                    f">{config.s5_threshold_on} minutes. "
                    f"Falling back to heat pump native curve."
                ),
            },
        },
        {
            "service": "input_boolean.turn_on",
            "target": {"entity_id": config.entity_watchdog_flag},
        },
    ]

    if config.entity_hp_thermostat is not None:
        actions.append(
            {
                "service": "climate.set_hvac_mode",
                "target": {"entity_id": config.entity_hp_thermostat},
                "data": {"hvac_mode": "heat"},
            },
        )

    return actions


def _build_s5_clear_actions(
    config: SafetyYAMLConfig,
) -> list[dict[str, object]]:
    """Build action list for the S5 watchdog clear automation.

    Actions include:
    - Notification about watchdog recovery.
    - Turn off the watchdog fallback flag (``input_boolean``).

    Args:
        config: Global safety YAML configuration.

    Returns:
        List of HA action dicts.
    """
    return [
        {
            "service": "persistent_notification.create",
            "data": {
                "title": "PumpAhead Safety S5",
                "message": (
                    "PumpAhead watchdog cleared. "
                    "PumpAhead resuming control."
                ),
            },
        },
        {
            "service": "input_boolean.turn_off",
            "target": {"entity_id": config.entity_watchdog_flag},
        },
    ]


def _build_s5_automations(
    config: SafetyYAMLConfig,
) -> list[dict[str, object]]:
    """Build S5 watchdog trigger + clear automations (global).

    S5 is global (not per-room).  Uses ``template`` triggers to
    compute minutes since last PumpAhead update.

    Trigger: minutes since last update > threshold_on -> notification
    Clear: minutes since last update < threshold_off -> notification

    Args:
        config: Global safety YAML configuration.

    Returns:
        List of two automation dicts (trigger + clear).
    """
    trigger_template = (
        f"{{% set last = states('{config.entity_pumpahead_last_update}') %}}\n"
        "{% if last not in ['unknown', 'unavailable', 'none', None] %}\n"
        "  {% set age_min = "
        "(now() - last | as_datetime).total_seconds() / 60 %}\n"
        f"  {{{{ age_min > {config.s5_threshold_on} }}}}\n"
        "{% else %}\n"
        "  {{ true }}\n"
        "{% endif %}"
    )

    clear_template = (
        f"{{% set last = states('{config.entity_pumpahead_last_update}') %}}\n"
        "{% if last not in ['unknown', 'unavailable', 'none', None] %}\n"
        "  {% set age_min = "
        "(now() - last | as_datetime).total_seconds() / 60 %}\n"
        f"  {{{{ age_min < {config.s5_threshold_off} }}}}\n"
        "{% else %}\n"
        "  {{ false }}\n"
        "{% endif %}"
    )

    trigger_auto: dict[str, object] = {
        "id": "pumpahead_s5_watchdog_trigger",
        "alias": "PumpAhead S5: Watchdog Trigger",
        "description": (
            f"Safety rule S5: PumpAhead has not updated for "
            f">{config.s5_threshold_on} minutes. Fallback to HP curve."
        ),
        "mode": "single",
        "trigger": [
            {
                "platform": "template",
                "value_template": trigger_template,
            },
        ],
        "condition": [],
        "action": _build_s5_trigger_actions(config),
    }

    clear_auto: dict[str, object] = {
        "id": "pumpahead_s5_watchdog_clear",
        "alias": "PumpAhead S5: Watchdog Clear",
        "description": (
            f"Safety rule S5 clear: PumpAhead resumed updating "
            f"(last update < {config.s5_threshold_off} min ago)."
        ),
        "mode": "single",
        "trigger": [
            {
                "platform": "template",
                "value_template": clear_template,
            },
        ],
        "condition": [],
        "action": _build_s5_clear_actions(config),
    }

    return [trigger_auto, clear_auto]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_safety_yaml_for_room(
    room: RoomEntityConfig,
    config: SafetyYAMLConfig,
) -> str:
    """Generate safety YAML automations for a single room (S1-S4).

    Produces 8 automations (trigger + clear for S1, S2, S3, S4).
    S5 (watchdog) is global and not included here.

    Args:
        room: Room entity configuration.
        config: Global safety YAML configuration.

    Returns:
        YAML string containing the room's safety automations.
    """
    automations: list[dict[str, object]] = []
    automations.extend(_build_s1_automations(room, config))
    automations.extend(_build_s2_automations(room, config))
    automations.extend(_build_s3_automations(room, config))
    automations.extend(_build_s4_automations(room, config))

    result: str = yaml.dump(
        automations,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )
    return result


def generate_safety_yaml(config: SafetyYAMLConfig) -> str:
    """Generate complete safety YAML automations for all rooms + watchdog.

    Produces per-room automations for S1-S4 (8 per room) plus
    2 global S5 watchdog automations.

    Args:
        config: Global safety YAML configuration with all rooms.

    Returns:
        YAML string containing all safety automations.  Can be
        appended to the user's ``automations.yaml``.
    """
    automations: list[dict[str, object]] = []

    for room in config.rooms:
        automations.extend(_build_s1_automations(room, config))
        automations.extend(_build_s2_automations(room, config))
        automations.extend(_build_s3_automations(room, config))
        automations.extend(_build_s4_automations(room, config))

    automations.extend(_build_s5_automations(config))

    result: str = yaml.dump(
        automations,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )
    return result
