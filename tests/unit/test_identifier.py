"""Comprehensive unit tests for pumpahead.identifier."""

import numpy as np
import pytest

from pumpahead.identifier import (
    DEFAULT_BOUNDS_2R2C,
    IdentificationResult,
    RCIdentifier,
)
from pumpahead.model import ModelOrder, RCModel, RCParams

# ---------------------------------------------------------------------------
# TestIdentificationResult — dataclass construction and validation
# ---------------------------------------------------------------------------


class TestIdentificationResult:
    """Tests for the IdentificationResult frozen dataclass."""

    @pytest.mark.unit
    def test_construction_valid(self, params_2r2c: RCParams) -> None:
        """Valid IdentificationResult can be constructed."""
        result = IdentificationResult(
            params=params_2r2c,
            cost=0.5,
            n_starts=3,
            converged=True,
            all_costs=(0.5, 0.8, 1.2),
        )
        assert result.cost == 0.5
        assert result.n_starts == 3
        assert result.converged is True
        assert len(result.all_costs) == 3

    @pytest.mark.unit
    def test_frozen(self, params_2r2c: RCParams) -> None:
        """IdentificationResult is immutable (frozen dataclass)."""
        result = IdentificationResult(
            params=params_2r2c,
            cost=0.5,
            n_starts=1,
            converged=True,
            all_costs=(0.5,),
        )
        with pytest.raises(AttributeError):
            result.cost = 1.0  # type: ignore[misc]

    @pytest.mark.unit
    def test_negative_cost_rejected(self, params_2r2c: RCParams) -> None:
        """Negative cost raises ValueError."""
        with pytest.raises(ValueError, match="cost must be non-negative"):
            IdentificationResult(
                params=params_2r2c,
                cost=-0.1,
                n_starts=1,
                converged=True,
                all_costs=(-0.1,),
            )

    @pytest.mark.unit
    def test_zero_n_starts_rejected(self, params_2r2c: RCParams) -> None:
        """n_starts < 1 raises ValueError."""
        with pytest.raises(ValueError, match="n_starts must be >= 1"):
            IdentificationResult(
                params=params_2r2c,
                cost=0.5,
                n_starts=0,
                converged=True,
                all_costs=(),
            )

    @pytest.mark.unit
    def test_all_costs_length_mismatch_rejected(
        self, params_2r2c: RCParams
    ) -> None:
        """all_costs length != n_starts raises ValueError."""
        with pytest.raises(ValueError, match="all_costs length"):
            IdentificationResult(
                params=params_2r2c,
                cost=0.5,
                n_starts=3,
                converged=True,
                all_costs=(0.5, 0.8),  # Only 2, but n_starts=3
            )


# ---------------------------------------------------------------------------
# TestRCIdentifierConstruction — constructor validation
# ---------------------------------------------------------------------------


class TestRCIdentifierConstruction:
    """Tests for RCIdentifier constructor."""

    @pytest.mark.unit
    def test_2r2c_defaults(self) -> None:
        """2R2C identifier with defaults has 4 parameters."""
        ident = RCIdentifier(ModelOrder.TWO)
        assert ident.n_params == 4
        assert ident.param_names == ["R_sf", "R_env", "C_air", "C_slab"]

    @pytest.mark.unit
    def test_3r3c_defaults(self) -> None:
        """3R3C identifier with R_ins has 7 parameters."""
        ident = RCIdentifier(ModelOrder.THREE, R_ins=0.01)
        assert ident.n_params == 7
        assert ident.param_names == [
            "R_sf",
            "R_wi",
            "R_wo",
            "R_ve",
            "C_air",
            "C_slab",
            "C_wall",
        ]

    @pytest.mark.unit
    def test_3r3c_missing_R_ins_rejected(self) -> None:
        """3R3C without R_ins raises ValueError."""
        with pytest.raises(ValueError, match="R_ins is required"):
            RCIdentifier(ModelOrder.THREE)

    @pytest.mark.unit
    def test_3r3c_negative_R_ins_rejected(self) -> None:
        """3R3C with R_ins <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="R_ins must be positive"):
            RCIdentifier(ModelOrder.THREE, R_ins=-0.01)

    @pytest.mark.unit
    def test_negative_dt_rejected(self) -> None:
        """dt <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="dt must be positive"):
            RCIdentifier(ModelOrder.TWO, dt=-1.0)

    @pytest.mark.unit
    def test_zero_n_starts_rejected(self) -> None:
        """n_starts < 1 raises ValueError."""
        with pytest.raises(ValueError, match="n_starts must be >= 1"):
            RCIdentifier(ModelOrder.TWO, n_starts=0)

    @pytest.mark.unit
    def test_custom_bounds_merged(self) -> None:
        """User bounds override defaults for specified keys."""
        custom = {"R_sf": (0.005, 0.05)}
        ident = RCIdentifier(ModelOrder.TWO, bounds=custom)
        assert ident._bounds_dict["R_sf"] == (0.005, 0.05)
        # Other bounds remain at defaults
        assert ident._bounds_dict["R_env"] == DEFAULT_BOUNDS_2R2C["R_env"]

    @pytest.mark.unit
    def test_param_names_returns_copy(self) -> None:
        """param_names returns a copy, not the internal list."""
        ident = RCIdentifier(ModelOrder.TWO)
        names = ident.param_names
        names.append("bogus")
        assert "bogus" not in ident.param_names


# ---------------------------------------------------------------------------
# TestRCIdentifierPackUnpack — parameter vector roundtrip
# ---------------------------------------------------------------------------


class TestRCIdentifierPackUnpack:
    """Tests for _pack_params and _unpack_params."""

    @pytest.mark.unit
    def test_roundtrip_2r2c(self, params_2r2c: RCParams) -> None:
        """Pack then unpack recovers original 2R2C parameters."""
        ident = RCIdentifier(ModelOrder.TWO)
        theta = ident._pack_params(params_2r2c)
        assert theta.shape == (4,)
        recovered = ident._unpack_params(theta)
        assert recovered.R_sf == pytest.approx(params_2r2c.R_sf)
        assert recovered.R_env == pytest.approx(params_2r2c.R_env)
        assert recovered.C_air == pytest.approx(params_2r2c.C_air)
        assert recovered.C_slab == pytest.approx(params_2r2c.C_slab)

    @pytest.mark.unit
    def test_roundtrip_3r3c(self, params_3r3c: RCParams) -> None:
        """Pack then unpack recovers original 3R3C parameters."""
        ident = RCIdentifier(
            ModelOrder.THREE,
            R_ins=0.01,
            f_conv=0.6,
            f_rad=0.4,
            T_ground=10.0,
        )
        theta = ident._pack_params(params_3r3c)
        assert theta.shape == (7,)
        recovered = ident._unpack_params(theta)
        assert recovered.R_sf == pytest.approx(params_3r3c.R_sf)
        assert recovered.R_wi == pytest.approx(params_3r3c.R_wi)
        assert recovered.R_wo == pytest.approx(params_3r3c.R_wo)
        assert recovered.R_ve == pytest.approx(params_3r3c.R_ve)
        assert recovered.C_air == pytest.approx(params_3r3c.C_air)
        assert recovered.C_slab == pytest.approx(params_3r3c.C_slab)
        assert recovered.C_wall == pytest.approx(params_3r3c.C_wall)

    @pytest.mark.unit
    def test_fixed_params_preserved_2r2c(self) -> None:
        """Fixed params (f_conv, f_rad, T_ground, has_split) are set correctly."""
        ident = RCIdentifier(
            ModelOrder.TWO,
            f_conv=0.7,
            f_rad=0.3,
            T_ground=12.0,
            has_split=False,
        )
        theta = np.array([0.01, 0.03, 60_000.0, 3_250_000.0])
        recovered = ident._unpack_params(theta)
        assert recovered.f_conv == 0.7
        assert recovered.f_rad == 0.3
        assert recovered.T_ground == 12.0
        assert recovered.has_split is False

    @pytest.mark.unit
    def test_fixed_params_preserved_3r3c(self) -> None:
        """Fixed R_ins is set correctly for 3R3C."""
        ident = RCIdentifier(ModelOrder.THREE, R_ins=0.015)
        theta = np.array([0.01, 0.02, 0.03, 0.03, 60_000.0, 3_250_000.0, 1_500_000.0])
        recovered = ident._unpack_params(theta)
        assert recovered.R_ins == 0.015


# ---------------------------------------------------------------------------
# TestRCIdentifierCostFunction — cost function correctness
# ---------------------------------------------------------------------------


class TestRCIdentifierCostFunction:
    """Tests for _cost_fn correctness."""

    @pytest.mark.unit
    def test_cost_zero_at_true_params(
        self,
        params_2r2c: RCParams,
        identifier_2r2c_synth_data: tuple[
            RCParams, np.ndarray, np.ndarray, np.ndarray
        ],
    ) -> None:
        """Cost is near zero when evaluated at the true parameters."""
        true_params, u_seq, d_seq, T_room = identifier_2r2c_synth_data
        ident = RCIdentifier(ModelOrder.TWO)
        theta_true = ident._pack_params(true_params)
        cost = ident._cost_fn(theta_true, u_seq, d_seq, T_room)
        assert cost == pytest.approx(0.0, abs=1e-5)

    @pytest.mark.unit
    def test_cost_positive_at_perturbed_params(
        self,
        identifier_2r2c_synth_data: tuple[
            RCParams, np.ndarray, np.ndarray, np.ndarray
        ],
    ) -> None:
        """Cost is positive when parameters differ from truth."""
        true_params, u_seq, d_seq, T_room = identifier_2r2c_synth_data
        ident = RCIdentifier(ModelOrder.TWO)
        theta_true = ident._pack_params(true_params)
        # Double all parameters
        theta_perturbed = theta_true * 2.0
        cost = ident._cost_fn(theta_perturbed, u_seq, d_seq, T_room)
        assert cost > 0.1

    @pytest.mark.unit
    def test_cost_returns_inf_on_invalid_params(self) -> None:
        """Cost returns inf for non-physical parameters."""
        ident = RCIdentifier(ModelOrder.TWO)
        # Negative values in theta will cause RCParams validation to fail
        theta_bad = np.array([-0.01, -0.03, -60_000.0, -3_250_000.0])
        u_seq = np.zeros((10, 1))
        d_seq = np.zeros((10, 2))
        T_room = np.full(10, 20.0)
        cost = ident._cost_fn(theta_bad, u_seq, d_seq, T_room)
        assert cost == float("inf")


# ---------------------------------------------------------------------------
# TestRCIdentifier2R2CConvergence — 2R2C identification recovery
# ---------------------------------------------------------------------------


class TestRCIdentifier2R2CConvergence:
    """Tests for 2R2C parameter recovery from synthetic data.

    Uses prior-informed bounds (±15 % of true values) to break the
    structural non-identifiability between R_sf and C_air that arises
    when only T_air is observed (not T_slab). In real usage the user
    derives similar priors from construction plans (slab mass, room
    volume, insulation thickness).
    """

    # Informed bounds: ±15 % around true values
    _INFORMED_BOUNDS: dict[str, tuple[float, float]] = {
        "R_sf": (0.0085, 0.0115),
        "R_env": (0.0255, 0.0345),
        "C_air": (51_000.0, 69_000.0),
        "C_slab": (2_762_500.0, 3_737_500.0),
    }

    @pytest.mark.unit
    def test_recovers_params_within_10_percent(
        self,
        identifier_2r2c_synth_data: tuple[
            RCParams, np.ndarray, np.ndarray, np.ndarray
        ],
    ) -> None:
        """2R2C identification recovers all 4 parameters within 10% error."""
        true_params, u_seq, d_seq, T_room = identifier_2r2c_synth_data
        ident = RCIdentifier(
            ModelOrder.TWO,
            n_starts=20,
            seed=42,
            bounds=self._INFORMED_BOUNDS,
        )
        result = ident.identify(u_seq, d_seq, T_room)

        # Check each parameter within 10% relative error
        assert result.params.R_sf == pytest.approx(
            true_params.R_sf, rel=0.10
        )
        assert result.params.R_env == pytest.approx(
            true_params.R_env, rel=0.10
        )
        assert result.params.C_air == pytest.approx(
            true_params.C_air, rel=0.10
        )
        assert result.params.C_slab == pytest.approx(
            true_params.C_slab, rel=0.10
        )

    @pytest.mark.unit
    def test_best_of_n_starts(
        self,
        identifier_2r2c_synth_data: tuple[
            RCParams, np.ndarray, np.ndarray, np.ndarray
        ],
    ) -> None:
        """Best cost equals minimum of all_costs."""
        _, u_seq, d_seq, T_room = identifier_2r2c_synth_data
        ident = RCIdentifier(
            ModelOrder.TWO,
            n_starts=5,
            seed=42,
            bounds=self._INFORMED_BOUNDS,
        )
        result = ident.identify(u_seq, d_seq, T_room)

        assert result.n_starts == 5
        assert len(result.all_costs) == 5
        assert result.cost == result.all_costs[0]  # Sorted ascending
        assert result.cost == min(result.all_costs)

    @pytest.mark.unit
    def test_converged_flag_set(
        self,
        identifier_2r2c_synth_data: tuple[
            RCParams, np.ndarray, np.ndarray, np.ndarray
        ],
    ) -> None:
        """Converged flag is True for well-conditioned synthetic data."""
        _, u_seq, d_seq, T_room = identifier_2r2c_synth_data
        ident = RCIdentifier(
            ModelOrder.TWO,
            n_starts=5,
            seed=42,
            bounds=self._INFORMED_BOUNDS,
        )
        result = ident.identify(u_seq, d_seq, T_room)
        assert result.converged is True

    @pytest.mark.unit
    def test_cost_near_zero_on_noiseless_data(
        self,
        identifier_2r2c_synth_data: tuple[
            RCParams, np.ndarray, np.ndarray, np.ndarray
        ],
    ) -> None:
        """Identification achieves near-zero cost on noiseless data."""
        _, u_seq, d_seq, T_room = identifier_2r2c_synth_data
        ident = RCIdentifier(
            ModelOrder.TWO,
            n_starts=10,
            seed=42,
            bounds=self._INFORMED_BOUNDS,
        )
        result = ident.identify(u_seq, d_seq, T_room)
        assert result.cost < 0.01  # MSE < 0.01 degC^2


# ---------------------------------------------------------------------------
# TestRCIdentifier3R3CConvergence — 3R3C identification recovery
# ---------------------------------------------------------------------------


class TestRCIdentifier3R3CConvergence:
    """Tests for 3R3C parameter recovery from synthetic data.

    Uses ±15 % prior-informed bounds, same rationale as the 2R2C tests.
    """

    _INFORMED_BOUNDS_3R3C: dict[str, tuple[float, float]] = {
        "R_sf": (0.0085, 0.0115),
        "R_wi": (0.017, 0.023),
        "R_wo": (0.0255, 0.0345),
        "R_ve": (0.0255, 0.0345),
        "C_air": (51_000.0, 69_000.0),
        "C_slab": (2_762_500.0, 3_737_500.0),
        "C_wall": (1_275_000.0, 1_725_000.0),
    }

    @pytest.fixture()
    def synth_3r3c_data(
        self,
        params_3r3c: RCParams,
        model_3r3c: RCModel,
    ) -> tuple[RCParams, np.ndarray, np.ndarray, np.ndarray]:
        """Synthetic 3R3C identification data: cyclic heating, 4 days at dt=60s.

        Starts from equilibrium at T_out = T_ground = 10 C, then
        alternates Q_floor between 0 and 1500 W in 4-hour blocks.
        First block is OFF so x0 matches cost function exactly.
        """
        n_steps = 5760  # 4 days for 3R3C (more params need longer data)
        u_seq = np.zeros((n_steps, 1))
        for i in range(n_steps):
            block = (i // 240) % 2
            u_seq[i, 0] = 0.0 if block == 0 else 1500.0

        d_seq = np.zeros((n_steps, 3))
        d_seq[:, 0] = 10.0  # constant T_out = T_ground = 10 C

        # Start from equilibrium: T_air = T_slab = T_wall = T_out = T_ground
        x0 = np.array([10.0, 10.0, 10.0])
        traj = model_3r3c.predict(x0, u_seq, d_seq)
        T_room = traj[1:, 0]
        return params_3r3c, u_seq, d_seq, T_room

    @pytest.mark.unit
    def test_recovers_params_within_10_percent(
        self,
        synth_3r3c_data: tuple[
            RCParams, np.ndarray, np.ndarray, np.ndarray
        ],
    ) -> None:
        """3R3C identification recovers 7 parameters within 10% error.

        Note: R_ins is fixed (not identified). Some weakly identifiable
        parameters (R_wo, C_wall) may need the full tolerance.
        """
        true_params, u_seq, d_seq, T_room = synth_3r3c_data
        assert true_params.R_ins is not None
        ident = RCIdentifier(
            ModelOrder.THREE,
            R_ins=true_params.R_ins,
            f_conv=true_params.f_conv,
            f_rad=true_params.f_rad,
            T_ground=true_params.T_ground,
            n_starts=10,
            seed=42,
            bounds=self._INFORMED_BOUNDS_3R3C,
        )
        result = ident.identify(u_seq, d_seq, T_room)

        assert result.params.R_sf == pytest.approx(
            true_params.R_sf, rel=0.10
        )
        assert result.params.R_wi == pytest.approx(
            true_params.R_wi, rel=0.10
        )
        assert result.params.R_wo == pytest.approx(
            true_params.R_wo, rel=0.10
        )
        assert result.params.R_ve == pytest.approx(
            true_params.R_ve, rel=0.10
        )
        assert result.params.C_air == pytest.approx(
            true_params.C_air, rel=0.10
        )
        assert result.params.C_slab == pytest.approx(
            true_params.C_slab, rel=0.10
        )
        assert result.params.C_wall == pytest.approx(
            true_params.C_wall, rel=0.10
        )

    @pytest.mark.unit
    def test_cost_near_zero_on_noiseless_data(
        self,
        synth_3r3c_data: tuple[
            RCParams, np.ndarray, np.ndarray, np.ndarray
        ],
    ) -> None:
        """3R3C identification achieves near-zero cost on noiseless data."""
        true_params, u_seq, d_seq, T_room = synth_3r3c_data
        assert true_params.R_ins is not None
        ident = RCIdentifier(
            ModelOrder.THREE,
            R_ins=true_params.R_ins,
            f_conv=true_params.f_conv,
            f_rad=true_params.f_rad,
            T_ground=true_params.T_ground,
            n_starts=10,
            seed=42,
            bounds=self._INFORMED_BOUNDS_3R3C,
        )
        result = ident.identify(u_seq, d_seq, T_room)
        assert result.cost < 0.01


# ---------------------------------------------------------------------------
# TestRCIdentifierBoxConstraints — bounds enforcement
# ---------------------------------------------------------------------------


class TestRCIdentifierBoxConstraints:
    """Tests for box constraint enforcement."""

    @pytest.mark.unit
    def test_params_within_default_bounds(
        self,
        identifier_2r2c_synth_data: tuple[
            RCParams, np.ndarray, np.ndarray, np.ndarray
        ],
    ) -> None:
        """All identified parameters lie within default bounds."""
        _, u_seq, d_seq, T_room = identifier_2r2c_synth_data
        ident = RCIdentifier(ModelOrder.TWO, n_starts=5, seed=42)
        result = ident.identify(u_seq, d_seq, T_room)

        for name, (lo, hi) in DEFAULT_BOUNDS_2R2C.items():
            value = getattr(result.params, name)
            assert lo <= value <= hi, (
                f"{name}={value} outside bounds [{lo}, {hi}]"
            )

    @pytest.mark.unit
    def test_custom_narrow_bounds(
        self,
        identifier_2r2c_synth_data: tuple[
            RCParams, np.ndarray, np.ndarray, np.ndarray
        ],
    ) -> None:
        """Narrow custom bounds constrain the solution."""
        _, u_seq, d_seq, T_room = identifier_2r2c_synth_data
        # Narrow bounds around the true values
        narrow_bounds = {
            "R_sf": (0.008, 0.012),
            "R_env": (0.025, 0.035),
            "C_air": (50_000.0, 70_000.0),
            "C_slab": (3_000_000.0, 3_500_000.0),
        }
        ident = RCIdentifier(
            ModelOrder.TWO, n_starts=3, seed=42, bounds=narrow_bounds
        )
        result = ident.identify(u_seq, d_seq, T_room)

        for name, (lo, hi) in narrow_bounds.items():
            value = getattr(result.params, name)
            assert lo <= value <= hi, (
                f"{name}={value} outside narrow bounds [{lo}, {hi}]"
            )


# ---------------------------------------------------------------------------
# TestRCIdentifierEdgeCases — validation and edge cases
# ---------------------------------------------------------------------------


class TestRCIdentifierEdgeCases:
    """Tests for input validation and edge cases."""

    @pytest.mark.unit
    def test_mismatched_u_d_lengths_rejected(self) -> None:
        """Mismatched u_sequence and d_sequence lengths raise ValueError."""
        ident = RCIdentifier(ModelOrder.TWO, n_starts=1)
        u = np.zeros((100, 1))
        d = np.zeros((50, 2))  # Different length
        T = np.zeros(100)
        with pytest.raises(ValueError, match="Sequence lengths must match"):
            ident.identify(u, d, T)

    @pytest.mark.unit
    def test_mismatched_T_room_length_rejected(self) -> None:
        """Mismatched T_room_measured length raises ValueError."""
        ident = RCIdentifier(ModelOrder.TWO, n_starts=1)
        u = np.zeros((100, 1))
        d = np.zeros((100, 2))
        T = np.zeros(50)  # Different length
        with pytest.raises(ValueError, match="Sequence lengths must match"):
            ident.identify(u, d, T)

    @pytest.mark.unit
    def test_1d_u_sequence_rejected(self) -> None:
        """1D u_sequence raises ValueError."""
        ident = RCIdentifier(ModelOrder.TWO, n_starts=1)
        u = np.zeros(100)  # 1D instead of 2D
        d = np.zeros((100, 2))
        T = np.zeros(100)
        with pytest.raises(ValueError, match="u_sequence must be 2D"):
            ident.identify(u, d, T)

    @pytest.mark.unit
    def test_1d_d_sequence_rejected(self) -> None:
        """1D d_sequence raises ValueError."""
        ident = RCIdentifier(ModelOrder.TWO, n_starts=1)
        u = np.zeros((100, 1))
        d = np.zeros(100)  # 1D instead of 2D
        T = np.zeros(100)
        with pytest.raises(ValueError, match="d_sequence must be 2D"):
            ident.identify(u, d, T)

    @pytest.mark.unit
    def test_2d_T_room_rejected(self) -> None:
        """2D T_room_measured raises ValueError."""
        ident = RCIdentifier(ModelOrder.TWO, n_starts=1)
        u = np.zeros((100, 1))
        d = np.zeros((100, 2))
        T = np.zeros((100, 1))  # 2D instead of 1D
        with pytest.raises(ValueError, match="T_room_measured must be 1D"):
            ident.identify(u, d, T)

    @pytest.mark.unit
    def test_single_start(
        self,
        identifier_2r2c_synth_data: tuple[
            RCParams, np.ndarray, np.ndarray, np.ndarray
        ],
    ) -> None:
        """Single start (n_starts=1) produces valid result."""
        _, u_seq, d_seq, T_room = identifier_2r2c_synth_data
        ident = RCIdentifier(ModelOrder.TWO, n_starts=1, seed=42)
        result = ident.identify(u_seq, d_seq, T_room)

        assert result.n_starts == 1
        assert len(result.all_costs) == 1
        assert result.cost >= 0.0

    @pytest.mark.unit
    def test_short_data_still_converges(self) -> None:
        """Short data series (100 steps) still produces a result."""
        # Create minimal synthetic data
        params = RCParams(
            C_air=60_000,
            C_slab=3_250_000,
            R_sf=0.01,
            R_env=0.03,
        )
        model = RCModel(params, ModelOrder.TWO, dt=60.0)
        n_steps = 100
        u_seq = np.full((n_steps, 1), 1500.0)
        d_seq = np.zeros((n_steps, 2))
        x0 = np.array([15.0, 15.0])
        traj = model.predict(x0, u_seq, d_seq)
        T_room = traj[1:, 0]

        ident = RCIdentifier(ModelOrder.TWO, n_starts=3, seed=42)
        result = ident.identify(u_seq, d_seq, T_room)

        assert result.cost >= 0.0
        assert result.n_starts == 3

    @pytest.mark.unit
    def test_all_costs_sorted_ascending(
        self,
        identifier_2r2c_synth_data: tuple[
            RCParams, np.ndarray, np.ndarray, np.ndarray
        ],
    ) -> None:
        """all_costs tuple is sorted in ascending order."""
        _, u_seq, d_seq, T_room = identifier_2r2c_synth_data
        ident = RCIdentifier(ModelOrder.TWO, n_starts=5, seed=42)
        result = ident.identify(u_seq, d_seq, T_room)

        for i in range(len(result.all_costs) - 1):
            assert result.all_costs[i] <= result.all_costs[i + 1]
