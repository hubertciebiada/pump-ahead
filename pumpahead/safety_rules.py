"""Safety rule definitions S1-S5 with hysteresis and configurable thresholds.

Provides frozen dataclass rules for floor overheat protection (S1),
condensation protection (S2), emergency heating (S3), emergency
cooling (S4), and watchdog timeout (S5).  Each rule is a
``SafetyRule`` constant; the ``SafetyEvaluator`` class tracks
per-rule hysteresis state so that a rule that triggers at the "on"
threshold stays active until the "off" threshold is crossed.

Design principles:
    * Safety is independent of the algorithm (Axiom #6).
    * T_floor <= 34 C hard limit (Axiom #4).
    * T_floor >= T_dew + 2 C condensation protection (Axiom #5).
    * Priority ordering: floor safety (1) > room emergency (2) > watchdog (3).
    * Rules are frozen dataclass instances -- data, not class hierarchy.
    * Thresholds are user-configurable via ``SafetyRule`` replacement.

Units:
    Temperatures: degC
    Humidity: % (0-100)
    Time: minutes (for watchdog)
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from pumpahead.simulator import HeatPumpMode

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class SafetyAction(Enum):
    """Action to take when a safety rule triggers.

    Members:
        CLOSE_VALVE: Set UFH valve to 0 % (S1 overheat, S2 condensation).
        EMERGENCY_HEAT: Valve 100 % + activate split heating (S3).
        EMERGENCY_COOL: Activate split cooling (S4).
        FALLBACK_HP_CURVE: Defer to heat pump native heating curve (S5).
    """

    CLOSE_VALVE = "close_valve"
    EMERGENCY_HEAT = "emergency_heat"
    EMERGENCY_COOL = "emergency_cool"
    FALLBACK_HP_CURVE = "fallback_hp_curve"


# ---------------------------------------------------------------------------
# Input snapshot
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SensorSnapshot:
    """Immutable sensor reading used as input for safety evaluation.

    All fields required for evaluating rules S1-S5.

    Attributes:
        T_floor: Floor / slab surface temperature [degC].
        T_room: Room air temperature [degC].
        humidity: Relative humidity [%] (0-100).
        hp_mode: Current heat pump operating mode.
        last_update_age_minutes: Minutes since last successful algorithm
            update (for S5 watchdog).
    """

    T_floor: float
    T_room: float
    humidity: float
    hp_mode: HeatPumpMode
    last_update_age_minutes: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.humidity <= 100.0:
            msg = f"humidity must be in [0, 100], got {self.humidity}"
            raise ValueError(msg)
        if self.last_update_age_minutes < 0.0:
            msg = (
                "last_update_age_minutes must be >= 0, "
                f"got {self.last_update_age_minutes}"
            )
            raise ValueError(msg)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _dew_point(t_air: float, rh: float) -> float:
    """Compute dew-point temperature using the simplified Magnus formula.

    Same approximation as in ``metrics.py``:
    ``T_dew = T_air - (100 - RH) / 5``.

    Args:
        t_air: Air temperature [degC].
        rh: Relative humidity [%] (0-100).

    Returns:
        Estimated dew-point temperature [degC].
    """
    return t_air - (100.0 - rh) / 5.0


# ---------------------------------------------------------------------------
# Safety rule dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SafetyRule:
    """Frozen definition of a single safety rule.

    Each rule consists of on/off thresholds (hysteresis), a priority,
    and a ``condition`` callable that extracts the measured value from
    a ``SensorSnapshot``.

    When ``trigger_above`` is ``True``, the rule activates when
    ``condition(snapshot) > threshold_on`` and clears when
    ``condition(snapshot) < threshold_off``.  When ``False``, the
    inequality is reversed (useful for "too cold" rules).

    Attributes:
        name: Rule identifier (e.g., ``"S1_floor_overheat"``).
        description: Human-readable description.
        priority: Lower number = higher priority (1 is highest).
        threshold_on: Value at which the rule triggers.
        threshold_off: Value at which the rule clears (hysteresis).
        action: ``SafetyAction`` to execute when triggered.
        condition: Callable extracting the measured value from a snapshot.
        trigger_above: If ``True``, triggers when measured > on; if
            ``False``, triggers when measured < on.
    """

    name: str
    description: str
    priority: int
    threshold_on: float
    threshold_off: float
    action: SafetyAction
    condition: Callable[[SensorSnapshot], float]
    trigger_above: bool

    def __post_init__(self) -> None:
        if not self.name:
            msg = "SafetyRule name must be non-empty"
            raise ValueError(msg)
        if self.priority < 1:
            msg = f"priority must be >= 1, got {self.priority}"
            raise ValueError(msg)
        if self.trigger_above and self.threshold_off > self.threshold_on:
            msg = (
                f"trigger_above rule '{self.name}': threshold_off "
                f"({self.threshold_off}) must be <= threshold_on "
                f"({self.threshold_on})"
            )
            raise ValueError(msg)
        if not self.trigger_above and self.threshold_off < self.threshold_on:
            msg = (
                f"trigger_below rule '{self.name}': threshold_off "
                f"({self.threshold_off}) must be >= threshold_on "
                f"({self.threshold_on})"
            )
            raise ValueError(msg)


# ---------------------------------------------------------------------------
# Evaluation result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SafetyRuleResult:
    """Immutable result of evaluating a single safety rule.

    Attributes:
        rule: The rule that was evaluated.
        triggered: Whether the rule is currently active.
        measured_value: Value extracted by ``rule.condition(snapshot)``.
        action: Action to take, or ``None`` if the rule is not triggered.
    """

    rule: SafetyRule
    triggered: bool
    measured_value: float
    action: SafetyAction | None


# ---------------------------------------------------------------------------
# Default rule constants
# ---------------------------------------------------------------------------

S1_FLOOR_OVERHEAT: SafetyRule = SafetyRule(
    name="S1_floor_overheat",
    description="Floor overheat protection (Axiom #4: T_floor <= 34C)",
    priority=1,
    threshold_on=34.0,
    threshold_off=33.0,
    action=SafetyAction.CLOSE_VALVE,
    condition=lambda s: s.T_floor,
    trigger_above=True,
)
"""S1: Close valve when T_floor > 34 degC, clear at T_floor < 33 degC."""

S2_CONDENSATION: SafetyRule = SafetyRule(
    name="S2_condensation",
    description="Condensation protection (Axiom #5: T_floor >= T_dew + 2C)",
    priority=1,
    threshold_on=0.0,
    threshold_off=1.0,
    action=SafetyAction.CLOSE_VALVE,
    condition=lambda s: s.T_floor - (_dew_point(s.T_room, s.humidity) + 2.0),
    trigger_above=False,
)
"""S2: Close valve when condensation margin < 0, clear at margin > 1."""

S3_EMERGENCY_HEAT: SafetyRule = SafetyRule(
    name="S3_emergency_heat",
    description="Emergency heating (T_room < 5C)",
    priority=2,
    threshold_on=5.0,
    threshold_off=6.0,
    action=SafetyAction.EMERGENCY_HEAT,
    condition=lambda s: s.T_room,
    trigger_above=False,
)
"""S3: Emergency heat when T_room < 5 degC, clear at T_room > 6 degC."""

S4_EMERGENCY_COOL: SafetyRule = SafetyRule(
    name="S4_emergency_cool",
    description="Emergency cooling (T_room > T_max)",
    priority=2,
    threshold_on=35.0,
    threshold_off=34.0,
    action=SafetyAction.EMERGENCY_COOL,
    condition=lambda s: s.T_room,
    trigger_above=True,
)
"""S4: Emergency cool when T_room > 35 degC, clear at T_room < 34 degC."""

S5_WATCHDOG: SafetyRule = SafetyRule(
    name="S5_watchdog",
    description="Watchdog timeout (no update > 15 min)",
    priority=3,
    threshold_on=15.0,
    threshold_off=5.0,
    action=SafetyAction.FALLBACK_HP_CURVE,
    condition=lambda s: s.last_update_age_minutes,
    trigger_above=True,
)
"""S5: Fallback to HP curve when no update for > 15 min, clear at < 5 min."""

DEFAULT_SAFETY_RULES: tuple[SafetyRule, ...] = (
    S1_FLOOR_OVERHEAT,
    S2_CONDENSATION,
    S3_EMERGENCY_HEAT,
    S4_EMERGENCY_COOL,
    S5_WATCHDOG,
)
"""All five default safety rules in priority order."""


# ---------------------------------------------------------------------------
# Stateful evaluator with hysteresis
# ---------------------------------------------------------------------------


class SafetyEvaluator:
    """Stateful safety evaluator with per-rule hysteresis tracking.

    Evaluates all configured safety rules against a ``SensorSnapshot``
    and tracks which rules are currently active.  A rule that triggers
    at its ``threshold_on`` stays active until the measured value crosses
    ``threshold_off`` in the recovery direction, preventing oscillation.

    Typical usage::

        evaluator = SafetyEvaluator()
        results = evaluator.evaluate(snapshot)
        for result in results:
            if result.triggered:
                apply_safety_action(result.action)

    Args:
        rules: Tuple of safety rules to evaluate.  Defaults to
            ``DEFAULT_SAFETY_RULES``.
    """

    def __init__(
        self,
        rules: tuple[SafetyRule, ...] = DEFAULT_SAFETY_RULES,
    ) -> None:
        self._rules = tuple(sorted(rules, key=lambda r: r.priority))
        self._active: dict[str, bool] = {r.name: False for r in self._rules}

    # -- Properties -----------------------------------------------------------

    @property
    def active_rule_names(self) -> list[str]:
        """Names of currently active (triggered) rules."""
        return [name for name, active in self._active.items() if active]

    # -- Public interface -----------------------------------------------------

    def evaluate(self, snapshot: SensorSnapshot) -> list[SafetyRuleResult]:
        """Evaluate all rules against *snapshot* with hysteresis.

        For each rule:
        - If ``trigger_above`` and not active: activate when
          ``measured > threshold_on``.
        - If ``trigger_above`` and active: deactivate when
          ``measured < threshold_off``.
        - If ``trigger_below`` and not active: activate when
          ``measured < threshold_on``.
        - If ``trigger_below`` and active: deactivate when
          ``measured > threshold_off``.

        Args:
            snapshot: Current sensor readings.

        Returns:
            List of ``SafetyRuleResult`` for every rule, sorted by
            priority (lowest number first).
        """
        results: list[SafetyRuleResult] = []

        for rule in self._rules:
            measured = rule.condition(snapshot)
            currently_active = self._active[rule.name]

            if rule.trigger_above:
                if not currently_active and measured > rule.threshold_on:
                    currently_active = True
                elif currently_active and measured < rule.threshold_off:
                    currently_active = False
            else:
                if not currently_active and measured < rule.threshold_on:
                    currently_active = True
                elif currently_active and measured > rule.threshold_off:
                    currently_active = False

            self._active[rule.name] = currently_active

            results.append(
                SafetyRuleResult(
                    rule=rule,
                    triggered=currently_active,
                    measured_value=measured,
                    action=rule.action if currently_active else None,
                )
            )

        return results

    def get_active_rules(self) -> list[SafetyRuleResult]:
        """Return results for currently triggered rules only.

        This is a convenience method that re-reads the internal active
        state without re-evaluating conditions.  Call :meth:`evaluate`
        first to refresh the state.

        Returns:
            List of ``SafetyRuleResult`` for active rules, sorted by
            priority.
        """
        active: list[SafetyRuleResult] = []
        for rule in self._rules:
            if self._active[rule.name]:
                active.append(
                    SafetyRuleResult(
                        rule=rule,
                        triggered=True,
                        measured_value=0.0,  # unknown without re-evaluation
                        action=rule.action,
                    )
                )
        return active

    def reset(self) -> None:
        """Clear all active states to ``False``."""
        for name in self._active:
            self._active[name] = False
