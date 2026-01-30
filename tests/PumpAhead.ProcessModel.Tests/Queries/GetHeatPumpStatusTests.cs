using FluentAssertions;
using NSubstitute;
using PumpAhead.DeepModel;
using PumpAhead.DeepModel.Aggregates;
using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.UseCases.Ports.Out;
using PumpAhead.UseCases.Queries.GetHeatPumpStatus;

namespace PumpAhead.ProcessModel.Tests.Queries;

public class GetHeatPumpStatusTests
{
    private const string HeatPumpModel = "HeatPumpModel";
    private const string DefaultErrorCode = "H00";
    private const string ErrorCodeH15 = "H15";
    private const string ExpectedOperatingMode = "HeatDhw";
    private const decimal PumpFlowLitersPerMinute = 12.5m;
    private const decimal OutsideTemperatureCelsius = 5.0m;
    private const decimal ChInletCelsius = 30.0m;
    private const decimal ChOutletCelsius = 35.0m;
    private const decimal ChTargetCelsius = 40.0m;
    private const decimal DhwActualCelsius = 48.0m;
    private const decimal DhwTargetCelsius = 50.0m;
    private const decimal CompressorFrequencyHertz = 45.0m;
    private const decimal HeatPowerProductionWatts = 5000m;
    private const decimal HeatPowerConsumptionWatts = 1200m;
    private const decimal ExpectedHeatingCop = 4.17m;
    private const decimal CompressorOperatingHours = 1234.5m;
    private const int CompressorStartCount = 567;
    private const decimal ErrorTestPumpFlowLitersPerMinute = 10.0m;
    private const decimal ErrorTestOutsideTemperatureCelsius = 0.0m;
    private const decimal ErrorTestChInletCelsius = 25.0m;
    private const decimal ErrorTestChTargetCelsius = 35.0m;
    private const decimal ErrorTestCompressorFrequencyHertz = 30.0m;
    private const decimal DefrostTestPumpFlowLitersPerMinute = 8.0m;
    private const decimal DefrostTestOutsideTemperatureCelsius = -5.0m;
    private const decimal DefrostTestChInletCelsius = 20.0m;
    private const decimal DefrostTestChOutletCelsius = 25.0m;
    private const decimal DefrostTestDhwActualCelsius = 40.0m;
    private const decimal ZeroFrequencyHertz = 0.0m;
    private const decimal ZeroPumpFlowLitersPerMinute = 0.0m;
    private const decimal OffTestOutsideTemperatureCelsius = 10.0m;
    private const decimal OffTestChCelsius = 20.0m;
    private const decimal DhwActualCelsius45 = 45.0m;

    private readonly IHeatPumpRepository _repository;
    private readonly GetHeatPumpStatus.Handler _handler;

    public GetHeatPumpStatusTests()
    {
        _repository = Substitute.For<IHeatPumpRepository>();
        _handler = new GetHeatPumpStatus.Handler(_repository);
    }

    #region Given-When-Then: ReturnsNull_WhenHeatPumpDoesNotExist

    [Fact]
    public async Task HandleAsync_ReturnsNull_WhenHeatPumpDoesNotExist()
    {
        // Given
        var heatPumpId = HeatPumpId.NewId();
        _repository
            .GetByIdAsync(heatPumpId, Arg.Any<CancellationToken>())
            .Returns((HeatPump?)null);

        // When
        var result = await _handler.HandleAsync(new GetHeatPumpStatus.Query(heatPumpId));

        // Then
        result.Should().BeNull();
    }

    #endregion

    #region Given-When-Then: ReturnsCorrectDto_WhenHeatPumpExists

    [Fact]
    public async Task HandleAsync_ReturnsCorrectDto_WhenHeatPumpExists()
    {
        // Given
        var heatPumpId = HeatPumpId.NewId();
        var lastSyncTime = DateTimeOffset.UtcNow;
        var heatPump = CreateTestHeatPump(heatPumpId, lastSyncTime);

        _repository
            .GetByIdAsync(heatPumpId, Arg.Any<CancellationToken>())
            .Returns(heatPump);

        // When
        var result = await _handler.HandleAsync(new GetHeatPumpStatus.Query(heatPumpId));

        // Then
        result.Should().NotBeNull();
        result!.Id.Should().Be(heatPumpId);
        result.Model.Should().Be(HeatPumpModel);
        result.LastSyncTime.Should().Be(lastSyncTime);
        result.IsOn.Should().BeTrue();
        result.OperatingMode.Should().Be(ExpectedOperatingMode);
        result.PumpFlowLitersPerMinute.Should().Be(PumpFlowLitersPerMinute);
        result.OutsideTemperatureCelsius.Should().Be(OutsideTemperatureCelsius);
        result.CH_InletTemperatureCelsius.Should().Be(ChInletCelsius);
        result.CH_OutletTemperatureCelsius.Should().Be(ChOutletCelsius);
        result.CH_TargetTemperatureCelsius.Should().Be(ChTargetCelsius);
        result.DHW_ActualTemperatureCelsius.Should().Be(DhwActualCelsius);
        result.DHW_TargetTemperatureCelsius.Should().Be(DhwTargetCelsius);
        result.CompressorFrequencyHertz.Should().Be(CompressorFrequencyHertz);
        result.HeatPowerProductionWatts.Should().Be(HeatPowerProductionWatts);
        result.HeatPowerConsumptionWatts.Should().Be(HeatPowerConsumptionWatts);
        result.HeatingCop.Should().Be(ExpectedHeatingCop);
        result.CompressorOperatingHours.Should().Be(CompressorOperatingHours);
        result.CompressorStartCount.Should().Be(CompressorStartCount);
        result.IsDefrosting.Should().BeFalse();
        result.ErrorCode.Should().Be(DefaultErrorCode);
        result.HasError.Should().BeFalse();
    }

    [Fact]
    public async Task HandleAsync_ReturnsCorrectErrorState_WhenHeatPumpHasError()
    {
        // Given
        var heatPumpId = HeatPumpId.NewId();
        var heatPump = CreateTestHeatPumpWithError(heatPumpId, "H15");

        _repository
            .GetByIdAsync(heatPumpId, Arg.Any<CancellationToken>())
            .Returns(heatPump);

        // When
        var result = await _handler.HandleAsync(new GetHeatPumpStatus.Query(heatPumpId));

        // Then
        result.Should().NotBeNull();
        result!.ErrorCode.Should().Be(ErrorCodeH15);
        result.HasError.Should().BeTrue();
    }

    [Fact]
    public async Task HandleAsync_ReturnsCorrectDefrostState_WhenHeatPumpIsDefrosting()
    {
        // Given
        var heatPumpId = HeatPumpId.NewId();
        var heatPump = CreateTestHeatPumpDefrosting(heatPumpId);

        _repository
            .GetByIdAsync(heatPumpId, Arg.Any<CancellationToken>())
            .Returns(heatPump);

        // When
        var result = await _handler.HandleAsync(new GetHeatPumpStatus.Query(heatPumpId));

        // Then
        result.Should().NotBeNull();
        result!.IsDefrosting.Should().BeTrue();
    }

    [Fact]
    public async Task HandleAsync_ReturnsCorrectState_WhenHeatPumpIsOff()
    {
        // Given
        var heatPumpId = HeatPumpId.NewId();
        var heatPump = CreateTestHeatPumpOff(heatPumpId);

        _repository
            .GetByIdAsync(heatPumpId, Arg.Any<CancellationToken>())
            .Returns(heatPump);

        // When
        var result = await _handler.HandleAsync(new GetHeatPumpStatus.Query(heatPumpId));

        // Then
        result.Should().NotBeNull();
        result!.IsOn.Should().BeFalse();
    }

    #endregion

    #region Test Data Builders

    private static HeatPump CreateTestHeatPump(HeatPumpId id, DateTimeOffset lastSyncTime)
    {
        return HeatPump.Reconstitute(
            id,
            "HeatPumpModel",
            lastSyncTime,
            isOn: true,
            OperatingMode.HeatDhw,
            PumpFlow.FromLitersPerMinute(PumpFlowLitersPerMinute),
            OutsideTemperature.FromCelsius(OutsideTemperatureCelsius),
            new CentralHeatingData(
                WaterTemperature.FromCelsius(ChInletCelsius),
                WaterTemperature.FromCelsius(ChOutletCelsius),
                WaterTemperature.FromCelsius(ChTargetCelsius)),
            new DomesticHotWaterData(
                DhwTemperature.FromCelsius(DhwActualCelsius),
                DhwTemperature.FromCelsius(DhwTargetCelsius)),
            Frequency.FromHertz(CompressorFrequencyHertz),
            new PowerData(
                Power.FromWatts(HeatPowerProductionWatts),
                Power.FromWatts(HeatPowerConsumptionWatts),
                Power.Zero,
                Power.Zero,
                Power.Zero,
                Power.Zero),
            new OperationsData(CompressorOperatingHours, CompressorStartCount),
            DefrostData.Inactive,
            ErrorCode.From(DefaultErrorCode));
    }

    private static HeatPump CreateTestHeatPumpWithError(HeatPumpId id, string errorCode)
    {
        return HeatPump.Reconstitute(
            id,
            "HeatPumpModel",
            DateTimeOffset.UtcNow,
            isOn: true,
            OperatingMode.HeatOnly,
            PumpFlow.FromLitersPerMinute(ErrorTestPumpFlowLitersPerMinute),
            OutsideTemperature.FromCelsius(ErrorTestOutsideTemperatureCelsius),
            new CentralHeatingData(
                WaterTemperature.FromCelsius(ErrorTestChInletCelsius),
                WaterTemperature.FromCelsius(ChInletCelsius),
                WaterTemperature.FromCelsius(ChOutletCelsius)),
            new DomesticHotWaterData(
                DhwTemperature.FromCelsius(DhwActualCelsius45),
                DhwTemperature.FromCelsius(DhwTargetCelsius)),
            Frequency.FromHertz(ErrorTestCompressorFrequencyHertz),
            PowerData.Zero,
            OperationsData.Zero,
            DefrostData.Inactive,
            ErrorCode.From(errorCode));
    }

    private static HeatPump CreateTestHeatPumpDefrosting(HeatPumpId id)
    {
        return HeatPump.Reconstitute(
            id,
            "HeatPumpModel",
            DateTimeOffset.UtcNow,
            isOn: true,
            OperatingMode.HeatOnly,
            PumpFlow.FromLitersPerMinute(DefrostTestPumpFlowLitersPerMinute),
            OutsideTemperature.FromCelsius(DefrostTestOutsideTemperatureCelsius),
            new CentralHeatingData(
                WaterTemperature.FromCelsius(DefrostTestChInletCelsius),
                WaterTemperature.FromCelsius(ErrorTestChInletCelsius),
                WaterTemperature.FromCelsius(ChOutletCelsius)),
            new DomesticHotWaterData(
                DhwTemperature.FromCelsius(DefrostTestDhwActualCelsius),
                DhwTemperature.FromCelsius(DhwTargetCelsius)),
            Frequency.FromHertz(ZeroFrequencyHertz),
            PowerData.Zero,
            OperationsData.Zero,
            DefrostData.Active,
            ErrorCode.None);
    }

    private static HeatPump CreateTestHeatPumpOff(HeatPumpId id)
    {
        return HeatPump.Reconstitute(
            id,
            "HeatPumpModel",
            DateTimeOffset.UtcNow,
            isOn: false,
            OperatingMode.HeatOnly,
            PumpFlow.FromLitersPerMinute(ZeroPumpFlowLitersPerMinute),
            OutsideTemperature.FromCelsius(OffTestOutsideTemperatureCelsius),
            new CentralHeatingData(
                WaterTemperature.FromCelsius(DefrostTestChInletCelsius),
                WaterTemperature.FromCelsius(DefrostTestChInletCelsius),
                WaterTemperature.FromCelsius(ChOutletCelsius)),
            new DomesticHotWaterData(
                DhwTemperature.FromCelsius(DhwActualCelsius45),
                DhwTemperature.FromCelsius(DhwTargetCelsius)),
            Frequency.FromHertz(ZeroFrequencyHertz),
            PowerData.Zero,
            OperationsData.Zero,
            DefrostData.Inactive,
            ErrorCode.None);
    }

    #endregion
}
