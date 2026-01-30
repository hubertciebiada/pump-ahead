using FluentAssertions;
using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.DeepModel.Tests.ValueObjects;

public class PowerDataTests
{
    #region PowerData.Zero

    [Fact]
    public void Zero_ShouldReturnPowerDataWithAllZeroValues()
    {
        // When
        var powerData = PowerData.Zero;

        // Then
        powerData.HeatProduction.Should().Be(Power.Zero);
        powerData.HeatConsumption.Should().Be(Power.Zero);
        powerData.CoolProduction.Should().Be(Power.Zero);
        powerData.CoolConsumption.Should().Be(Power.Zero);
        powerData.DhwProduction.Should().Be(Power.Zero);
        powerData.DhwConsumption.Should().Be(Power.Zero);
    }

    [Fact]
    public void Zero_ShouldHaveZeroHeatingCop()
    {
        // When
        var powerData = PowerData.Zero;

        // Then
        powerData.HeatingCop.Should().Be(0m);
    }

    [Fact]
    public void Zero_ShouldHaveZeroDhwCop()
    {
        // When
        var powerData = PowerData.Zero;

        // Then
        powerData.DhwCop.Should().Be(0m);
    }

    [Fact]
    public void Zero_ShouldHaveZeroTotalConsumption()
    {
        // When
        var powerData = PowerData.Zero;

        // Then
        powerData.TotalConsumption.Should().Be(Power.Zero);
    }

    #endregion

    #region HeatingCop - When Consumption Is Zero

    [Fact]
    public void HeatingCop_GivenZeroHeatConsumption_ShouldReturnZero()
    {
        // Given
        var powerData = new PowerData(
            HeatProduction: Power.FromWatts(5000m),
            HeatConsumption: Power.Zero,
            CoolProduction: Power.Zero,
            CoolConsumption: Power.Zero,
            DhwProduction: Power.Zero,
            DhwConsumption: Power.Zero);

        // When
        var cop = powerData.HeatingCop;

        // Then
        cop.Should().Be(0m);
    }

    [Fact]
    public void HeatingCop_GivenBothProductionAndConsumptionZero_ShouldReturnZero()
    {
        // Given
        var powerData = new PowerData(
            HeatProduction: Power.Zero,
            HeatConsumption: Power.Zero,
            CoolProduction: Power.Zero,
            CoolConsumption: Power.Zero,
            DhwProduction: Power.Zero,
            DhwConsumption: Power.Zero);

        // When
        var cop = powerData.HeatingCop;

        // Then
        cop.Should().Be(0m);
    }

    #endregion

    #region HeatingCop - When Consumption Is Greater Than Zero

    [Fact]
    public void HeatingCop_GivenPositiveConsumption_ShouldCalculateCopCorrectly()
    {
        // Given
        var powerData = new PowerData(
            HeatProduction: Power.FromWatts(4000m),
            HeatConsumption: Power.FromWatts(1000m),
            CoolProduction: Power.Zero,
            CoolConsumption: Power.Zero,
            DhwProduction: Power.Zero,
            DhwConsumption: Power.Zero);

        // When
        var cop = powerData.HeatingCop;

        // Then
        cop.Should().Be(4.00m);
    }

    [Fact]
    public void HeatingCop_GivenTypicalValues_ShouldReturnExpectedCop()
    {
        // Given - typical heat pump COP around 3.5
        var powerData = new PowerData(
            HeatProduction: Power.FromWatts(3500m),
            HeatConsumption: Power.FromWatts(1000m),
            CoolProduction: Power.Zero,
            CoolConsumption: Power.Zero,
            DhwProduction: Power.Zero,
            DhwConsumption: Power.Zero);

        // When
        var cop = powerData.HeatingCop;

        // Then
        cop.Should().Be(3.5m);
    }

    [Fact]
    public void HeatingCop_ShouldRoundToTwoDecimalPlaces()
    {
        // Given - values that would produce many decimal places
        var powerData = new PowerData(
            HeatProduction: Power.FromWatts(3333m),
            HeatConsumption: Power.FromWatts(1000m),
            CoolProduction: Power.Zero,
            CoolConsumption: Power.Zero,
            DhwProduction: Power.Zero,
            DhwConsumption: Power.Zero);

        // When
        var cop = powerData.HeatingCop;

        // Then
        cop.Should().Be(3.33m);
    }

    [Fact]
    public void HeatingCop_GivenProductionLessThanConsumption_ShouldReturnCopLessThanOne()
    {
        // Given - inefficient scenario
        var powerData = new PowerData(
            HeatProduction: Power.FromWatts(500m),
            HeatConsumption: Power.FromWatts(1000m),
            CoolProduction: Power.Zero,
            CoolConsumption: Power.Zero,
            DhwProduction: Power.Zero,
            DhwConsumption: Power.Zero);

        // When
        var cop = powerData.HeatingCop;

        // Then
        cop.Should().Be(0.5m);
    }

    #endregion

    #region DhwCop - When Consumption Is Zero

    [Fact]
    public void DhwCop_GivenZeroDhwConsumption_ShouldReturnZero()
    {
        // Given
        var powerData = new PowerData(
            HeatProduction: Power.Zero,
            HeatConsumption: Power.Zero,
            CoolProduction: Power.Zero,
            CoolConsumption: Power.Zero,
            DhwProduction: Power.FromWatts(3000m),
            DhwConsumption: Power.Zero);

        // When
        var cop = powerData.DhwCop;

        // Then
        cop.Should().Be(0m);
    }

    #endregion

    #region DhwCop - When Consumption Is Greater Than Zero

    [Fact]
    public void DhwCop_GivenPositiveConsumption_ShouldCalculateCopCorrectly()
    {
        // Given
        var powerData = new PowerData(
            HeatProduction: Power.Zero,
            HeatConsumption: Power.Zero,
            CoolProduction: Power.Zero,
            CoolConsumption: Power.Zero,
            DhwProduction: Power.FromWatts(3000m),
            DhwConsumption: Power.FromWatts(1000m));

        // When
        var cop = powerData.DhwCop;

        // Then
        cop.Should().Be(3.00m);
    }

    [Fact]
    public void DhwCop_ShouldRoundToTwoDecimalPlaces()
    {
        // Given
        var powerData = new PowerData(
            HeatProduction: Power.Zero,
            HeatConsumption: Power.Zero,
            CoolProduction: Power.Zero,
            CoolConsumption: Power.Zero,
            DhwProduction: Power.FromWatts(2777m),
            DhwConsumption: Power.FromWatts(1000m));

        // When
        var cop = powerData.DhwCop;

        // Then
        cop.Should().Be(2.78m);
    }

    #endregion

    #region TotalConsumption

    [Fact]
    public void TotalConsumption_GivenOnlyHeatConsumption_ShouldReturnHeatConsumptionValue()
    {
        // Given
        var powerData = new PowerData(
            HeatProduction: Power.Zero,
            HeatConsumption: Power.FromWatts(1000m),
            CoolProduction: Power.Zero,
            CoolConsumption: Power.Zero,
            DhwProduction: Power.Zero,
            DhwConsumption: Power.Zero);

        // When
        var total = powerData.TotalConsumption;

        // Then
        total.Watts.Should().Be(1000m);
    }

    [Fact]
    public void TotalConsumption_GivenOnlyCoolConsumption_ShouldReturnCoolConsumptionValue()
    {
        // Given
        var powerData = new PowerData(
            HeatProduction: Power.Zero,
            HeatConsumption: Power.Zero,
            CoolProduction: Power.Zero,
            CoolConsumption: Power.FromWatts(800m),
            DhwProduction: Power.Zero,
            DhwConsumption: Power.Zero);

        // When
        var total = powerData.TotalConsumption;

        // Then
        total.Watts.Should().Be(800m);
    }

    [Fact]
    public void TotalConsumption_GivenOnlyDhwConsumption_ShouldReturnDhwConsumptionValue()
    {
        // Given
        var powerData = new PowerData(
            HeatProduction: Power.Zero,
            HeatConsumption: Power.Zero,
            CoolProduction: Power.Zero,
            CoolConsumption: Power.Zero,
            DhwProduction: Power.Zero,
            DhwConsumption: Power.FromWatts(1500m));

        // When
        var total = powerData.TotalConsumption;

        // Then
        total.Watts.Should().Be(1500m);
    }

    [Fact]
    public void TotalConsumption_GivenAllConsumptionValues_ShouldSumAllConsumptions()
    {
        // Given
        var powerData = new PowerData(
            HeatProduction: Power.FromWatts(5000m),
            HeatConsumption: Power.FromWatts(1000m),
            CoolProduction: Power.FromWatts(3000m),
            CoolConsumption: Power.FromWatts(500m),
            DhwProduction: Power.FromWatts(2000m),
            DhwConsumption: Power.FromWatts(700m));

        // When
        var total = powerData.TotalConsumption;

        // Then
        total.Watts.Should().Be(2200m); // 1000 + 500 + 700
    }

    [Fact]
    public void TotalConsumption_GivenAllZeroConsumption_ShouldReturnZero()
    {
        // Given
        var powerData = new PowerData(
            HeatProduction: Power.FromWatts(5000m),
            HeatConsumption: Power.Zero,
            CoolProduction: Power.FromWatts(3000m),
            CoolConsumption: Power.Zero,
            DhwProduction: Power.FromWatts(2000m),
            DhwConsumption: Power.Zero);

        // When
        var total = powerData.TotalConsumption;

        // Then
        total.Should().Be(Power.Zero);
    }

    [Fact]
    public void TotalConsumption_ShouldNotIncludeProductionValues()
    {
        // Given - high production values but low consumption
        var powerData = new PowerData(
            HeatProduction: Power.FromWatts(10000m),
            HeatConsumption: Power.FromWatts(100m),
            CoolProduction: Power.FromWatts(10000m),
            CoolConsumption: Power.FromWatts(100m),
            DhwProduction: Power.FromWatts(10000m),
            DhwConsumption: Power.FromWatts(100m));

        // When
        var total = powerData.TotalConsumption;

        // Then
        total.Watts.Should().Be(300m); // Only consumption: 100 + 100 + 100
    }

    #endregion

    #region Record Equality

    [Fact]
    public void Equality_GivenSameValues_ShouldBeEqual()
    {
        // Given
        var powerData1 = new PowerData(
            HeatProduction: Power.FromWatts(1000m),
            HeatConsumption: Power.FromWatts(500m),
            CoolProduction: Power.FromWatts(800m),
            CoolConsumption: Power.FromWatts(400m),
            DhwProduction: Power.FromWatts(600m),
            DhwConsumption: Power.FromWatts(300m));

        var powerData2 = new PowerData(
            HeatProduction: Power.FromWatts(1000m),
            HeatConsumption: Power.FromWatts(500m),
            CoolProduction: Power.FromWatts(800m),
            CoolConsumption: Power.FromWatts(400m),
            DhwProduction: Power.FromWatts(600m),
            DhwConsumption: Power.FromWatts(300m));

        // Then
        powerData1.Should().Be(powerData2);
    }

    [Fact]
    public void Equality_GivenDifferentValues_ShouldNotBeEqual()
    {
        // Given
        var powerData1 = new PowerData(
            HeatProduction: Power.FromWatts(1000m),
            HeatConsumption: Power.FromWatts(500m),
            CoolProduction: Power.Zero,
            CoolConsumption: Power.Zero,
            DhwProduction: Power.Zero,
            DhwConsumption: Power.Zero);

        var powerData2 = new PowerData(
            HeatProduction: Power.FromWatts(2000m),
            HeatConsumption: Power.FromWatts(500m),
            CoolProduction: Power.Zero,
            CoolConsumption: Power.Zero,
            DhwProduction: Power.Zero,
            DhwConsumption: Power.Zero);

        // Then
        powerData1.Should().NotBe(powerData2);
    }

    #endregion

    #region Combined Scenarios

    [Fact]
    public void GivenTypicalHeatPumpOperation_ShouldCalculateCorrectMetrics()
    {
        // Given - typical winter operation with heating and DHW
        var powerData = new PowerData(
            HeatProduction: Power.FromWatts(7000m),
            HeatConsumption: Power.FromWatts(2000m),
            CoolProduction: Power.Zero,
            CoolConsumption: Power.Zero,
            DhwProduction: Power.FromWatts(4500m),
            DhwConsumption: Power.FromWatts(1500m));

        // Then
        powerData.HeatingCop.Should().Be(3.5m);
        powerData.DhwCop.Should().Be(3.00m);
        powerData.TotalConsumption.Watts.Should().Be(3500m); // 2000 + 0 + 1500
    }

    [Fact]
    public void GivenSummerCoolingOperation_ShouldCalculateCorrectMetrics()
    {
        // Given - summer operation with cooling and DHW
        var powerData = new PowerData(
            HeatProduction: Power.Zero,
            HeatConsumption: Power.Zero,
            CoolProduction: Power.FromWatts(5000m),
            CoolConsumption: Power.FromWatts(1200m),
            DhwProduction: Power.FromWatts(3000m),
            DhwConsumption: Power.FromWatts(1000m));

        // Then
        powerData.HeatingCop.Should().Be(0m); // No heating
        powerData.DhwCop.Should().Be(3.00m);
        powerData.TotalConsumption.Watts.Should().Be(2200m); // 0 + 1200 + 1000
    }

    #endregion
}
