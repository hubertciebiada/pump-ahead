using FluentAssertions;
using FluentAssertions.Execution;
using PumpAhead.DeepModel.Aggregates;
using PumpAhead.DeepModel.Entities;
using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.Tests.Common.Extensions;

/// <summary>
/// FluentAssertions extension methods for domain objects.
/// </summary>
public static class FluentAssertionExtensions
{
    /// <summary>
    /// Asserts that two HeatPump instances have the same state values.
    /// </summary>
    public static void ShouldBeEquivalentToState(this HeatPump actual, HeatPump expected)
    {
        using var _ = new AssertionScope();

        actual.Id.Should().Be(expected.Id);
        actual.Model.Should().Be(expected.Model);
        actual.IsOn.Should().Be(expected.IsOn);
        actual.OperatingMode.Should().Be(expected.OperatingMode);
        actual.PumpFlow.Should().Be(expected.PumpFlow);
        actual.OutsideTemperature.Should().Be(expected.OutsideTemperature);
        actual.CentralHeating.Should().Be(expected.CentralHeating);
        actual.DomesticHotWater.Should().Be(expected.DomesticHotWater);
        actual.CompressorFrequency.Should().Be(expected.CompressorFrequency);
        actual.Power.Should().Be(expected.Power);
        actual.Operations.Should().Be(expected.Operations);
        actual.Defrost.Should().Be(expected.Defrost);
        actual.ErrorCode.Should().Be(expected.ErrorCode);
    }

    /// <summary>
    /// Asserts that two HeatPumpSnapshot instances have the same state values.
    /// </summary>
    public static void ShouldBeEquivalentToState(this HeatPumpSnapshot actual, HeatPumpSnapshot expected)
    {
        using var _ = new AssertionScope();

        actual.HeatPumpId.Should().Be(expected.HeatPumpId);
        actual.IsOn.Should().Be(expected.IsOn);
        actual.OperatingMode.Should().Be(expected.OperatingMode);
        actual.PumpFlow.Should().Be(expected.PumpFlow);
        actual.OutsideTemperature.Should().Be(expected.OutsideTemperature);
        actual.CentralHeating.Should().Be(expected.CentralHeating);
        actual.DomesticHotWater.Should().Be(expected.DomesticHotWater);
        actual.CompressorFrequency.Should().Be(expected.CompressorFrequency);
        actual.Power.Should().Be(expected.Power);
        actual.Operations.Should().Be(expected.Operations);
        actual.Defrost.Should().Be(expected.Defrost);
        actual.ErrorCode.Should().Be(expected.ErrorCode);
    }

    /// <summary>
    /// Asserts that the temperature is within a specified tolerance.
    /// </summary>
    public static void ShouldBeCloseTo(this Temperature actual, Temperature expected, decimal tolerance = 0.1m)
    {
        actual.Celsius.Should().BeApproximately(expected.Celsius, tolerance,
            $"Temperature should be close to {expected}");
    }

    /// <summary>
    /// Asserts that the power value is within a specified tolerance.
    /// </summary>
    public static void ShouldBeCloseTo(this Power actual, Power expected, decimal tolerance = 1m)
    {
        actual.Watts.Should().BeApproximately(expected.Watts, tolerance,
            $"Power should be close to {expected}");
    }
}
