"""Entity validation for the PumpAhead config flow.

Validates entity ``unit_of_measurement``, ``device_class``, and
availability at config time.  This is a standalone utility class that
delegates to ``hass.states.get()`` -- it carries no HA base-class
inheritance and stores no state.

Axiom 8: hardware-agnostic.  Unit validation only (degC, %, W).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of a single entity validation check."""

    valid: bool
    error_key: str | None = None
    error_details: str | None = None


class EntityValidator:
    """Validates HA entities for unit, device_class, and availability.

    Designed for use in the config flow.  Instantiate with a live
    ``HomeAssistant`` instance and call :meth:`validate_entity` for
    composite checks or the individual ``validate_*`` methods.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass

    # -- Individual checks ---------------------------------------------------

    def validate_unit(
        self, entity_id: str, valid_units: set[str]
    ) -> ValidationResult:
        """Check that the entity's ``unit_of_measurement`` is acceptable.

        Returns success when the entity has no ``unit_of_measurement``
        attribute (some actuators may not declare units).
        """
        if not entity_id:
            return ValidationResult(valid=True)

        state = self._hass.states.get(entity_id)
        if state is None:
            return ValidationResult(
                valid=False,
                error_key="entity_not_found",
                error_details=f"Entity {entity_id} not found in Home Assistant",
            )

        unit = getattr(state, "attributes", {}).get("unit_of_measurement")
        if unit is None:
            return ValidationResult(valid=True)

        if unit not in valid_units:
            return ValidationResult(
                valid=False,
                error_key="invalid_unit",
                error_details=(
                    f"Entity {entity_id} has unit '{unit}', "
                    f"expected one of: {', '.join(sorted(valid_units))}"
                ),
            )

        return ValidationResult(valid=True)

    def validate_device_class(
        self, entity_id: str, expected_device_class: str
    ) -> ValidationResult:
        """Check the entity's ``device_class`` attribute.

        Returns success when the entity has no ``device_class``
        attribute (tolerance for entities that don't declare one).
        """
        if not entity_id:
            return ValidationResult(valid=True)

        state = self._hass.states.get(entity_id)
        if state is None:
            return ValidationResult(
                valid=False,
                error_key="entity_not_found",
                error_details=f"Entity {entity_id} not found in Home Assistant",
            )

        device_class = getattr(state, "attributes", {}).get("device_class")
        if device_class is None:
            return ValidationResult(valid=True)

        if device_class != expected_device_class:
            return ValidationResult(
                valid=False,
                error_key="invalid_device_class",
                error_details=(
                    f"Entity {entity_id} has device_class '{device_class}', "
                    f"expected '{expected_device_class}'"
                ),
            )

        return ValidationResult(valid=True)

    def validate_availability(self, entity_id: str) -> ValidationResult:
        """Check that the entity is not ``unavailable`` or ``unknown``.

        This is a config-time warning check.  The caller decides
        whether to block or merely log.
        """
        if not entity_id:
            return ValidationResult(valid=True)

        state = self._hass.states.get(entity_id)
        if state is None:
            return ValidationResult(
                valid=False,
                error_key="entity_not_found",
                error_details=f"Entity {entity_id} not found in Home Assistant",
            )

        if state.state in ("unavailable", "unknown"):
            return ValidationResult(
                valid=False,
                error_key="entity_unavailable",
                error_details=(
                    f"Entity {entity_id} is currently {state.state} "
                    "-- it may come online later"
                ),
            )

        return ValidationResult(valid=True)

    # -- Composite check -----------------------------------------------------

    def validate_entity(
        self,
        entity_id: str,
        valid_units: set[str] | None = None,
        expected_device_class: str | None = None,
    ) -> ValidationResult:
        """Run all applicable checks on a single entity.

        Order: existence -> availability (warning) -> device_class -> unit.
        Returns the first hard failure, or success.
        """
        if not entity_id:
            return ValidationResult(valid=True)

        # 1. Existence check.
        state = self._hass.states.get(entity_id)
        if state is None:
            return ValidationResult(
                valid=False,
                error_key="entity_not_found",
                error_details=f"Entity {entity_id} not found in Home Assistant",
            )

        # 2. Availability (warning only -- logged, not blocking).
        avail = self.validate_availability(entity_id)
        if not avail.valid and avail.error_key == "entity_unavailable":
            _LOGGER.warning("%s", avail.error_details)

        # 3. Device class (blocking if provided).
        if expected_device_class is not None:
            dc_result = self.validate_device_class(entity_id, expected_device_class)
            if not dc_result.valid and dc_result.error_key != "entity_unavailable":
                return dc_result

        # 4. Unit (blocking if provided).
        if valid_units is not None:
            unit_result = self.validate_unit(entity_id, valid_units)
            if not unit_result.valid:
                return unit_result

        return ValidationResult(valid=True)
