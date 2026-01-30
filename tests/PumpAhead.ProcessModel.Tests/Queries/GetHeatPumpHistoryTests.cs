using FluentAssertions;
using NSubstitute;
using PumpAhead.DeepModel;
using PumpAhead.DeepModel.Entities;
using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.UseCases.Ports.Out;
using PumpAhead.UseCases.Queries.GetHeatPumpHistory;

namespace PumpAhead.ProcessModel.Tests.Queries;

public class GetHeatPumpHistoryTests
{
    private const int HoursInDay = 24;
    private const int DaysInWeek = 7;
    private const int HoursIn12HourRange = 12;
    private const int HoursIn6HourRange = 6;
    private const int LargeDatasetSnapshots = 100;
    private const decimal DefaultPumpFlowLitersPerMinute = 10.0m;
    private const decimal OutsideTempCelsius5 = 5.0m;
    private const decimal OutsideTempCelsius6 = 6.0m;
    private const decimal OutsideTempCelsius7 = 7.0m;
    private const decimal OutsideTempCelsius8 = 8.0m;
    private const decimal OutsideTempCelsius10 = 10.0m;
    private const decimal OutsideTempCelsius5_5 = 5.5m;
    private const decimal ChOutletTempCelsius35 = 35.0m;
    private const decimal ChInletTempCelsius30 = 30.0m;
    private const decimal ChTargetTempCelsius40 = 40.0m;
    private const decimal DhwActualTempCelsius45 = 45.0m;
    private const decimal DhwActualTempCelsius48 = 48.0m;
    private const decimal DhwTargetTempCelsius50 = 50.0m;
    private const decimal CompressorFrequencyHertz40 = 40.0m;
    private const decimal CompressorFrequencyHertz45 = 45.0m;
    private const decimal CompressorFrequencyHertz0 = 0.0m;
    private const decimal PowerProductionWatts4000 = 4000m;
    private const decimal PowerConsumptionWatts1000 = 1000m;
    private const decimal PowerConsumptionWatts1200 = 1200m;
    private const decimal PowerConsumptionWatts500 = 500m;
    private const decimal OperationsCompressorHours = 1000m;
    private const int OperationsCompressorStarts = 100;
    private const decimal ExpectedCop4_17 = 4.17m;
    private const decimal OutsideTempDefrostCelsius = -5.0m;
    private const decimal ChOutletTempDefrostCelsius = 25.0m;

    private readonly IHeatPumpSnapshotRepository _repository;
    private readonly GetHeatPumpHistory.Handler _handler;

    public GetHeatPumpHistoryTests()
    {
        _repository = Substitute.For<IHeatPumpSnapshotRepository>();
        _handler = new GetHeatPumpHistory.Handler(_repository);
    }

    #region Given-When-Then: ReturnsEmptyList_WhenNoSnapshots

    [Fact]
    public async Task HandleAsync_ReturnsEmptyList_WhenNoSnapshotsExist()
    {
        // Given
        var heatPumpId = HeatPumpId.NewId();
        var from = DateTimeOffset.UtcNow.AddHours(-HoursInDay);
        var to = DateTimeOffset.UtcNow;

        _repository
            .GetHistoryAsync(heatPumpId, from, to, Arg.Any<CancellationToken>())
            .Returns(new List<HeatPumpSnapshot>());

        // When
        var result = await _handler.HandleAsync(new GetHeatPumpHistory.Query(heatPumpId, from, to));

        // Then
        result.Should().NotBeNull();
        result.History.Should().BeEmpty();
    }

    #endregion

    #region Given-When-Then: ReturnsSnapshotsInOrder

    [Fact]
    public async Task HandleAsync_ReturnsSnapshotsInCorrectOrder_WhenDataExists()
    {
        // Given
        var heatPumpId = HeatPumpId.NewId();
        var from = DateTimeOffset.UtcNow.AddHours(-HoursInDay);
        var to = DateTimeOffset.UtcNow;

        var timestamp1 = from.AddHours(1);
        var timestamp2 = from.AddHours(2);
        var timestamp3 = from.AddHours(3);

        var snapshots = new List<HeatPumpSnapshot>
        {
            CreateTestSnapshot(heatPumpId, 1, timestamp1, outsideTemp: OutsideTempCelsius5, isOn: true),
            CreateTestSnapshot(heatPumpId, 2, timestamp2, outsideTemp: OutsideTempCelsius6, isOn: true),
            CreateTestSnapshot(heatPumpId, 3, timestamp3, outsideTemp: OutsideTempCelsius7, isOn: true)
        };

        _repository
            .GetHistoryAsync(heatPumpId, from, to, Arg.Any<CancellationToken>())
            .Returns(snapshots);

        // When
        var result = await _handler.HandleAsync(new GetHeatPumpHistory.Query(heatPumpId, from, to));

        // Then
        result.History.Should().HaveCount(3);
        result.History[0].Timestamp.Should().Be(timestamp1);
        result.History[1].Timestamp.Should().Be(timestamp2);
        result.History[2].Timestamp.Should().Be(timestamp3);
    }

    [Fact]
    public async Task HandleAsync_PreservesTimestamps_WhenMappingSnapshots()
    {
        // Given
        var heatPumpId = HeatPumpId.NewId();
        var from = DateTimeOffset.UtcNow.AddHours(-HoursInDay);
        var to = DateTimeOffset.UtcNow;
        var exactTimestamp = from.AddHours(5).AddMinutes(30).AddSeconds(15);

        var snapshots = new List<HeatPumpSnapshot>
        {
            CreateTestSnapshot(heatPumpId, 1, exactTimestamp, outsideTemp: OutsideTempCelsius10, isOn: true)
        };

        _repository
            .GetHistoryAsync(heatPumpId, from, to, Arg.Any<CancellationToken>())
            .Returns(snapshots);

        // When
        var result = await _handler.HandleAsync(new GetHeatPumpHistory.Query(heatPumpId, from, to));

        // Then
        result.History.Should().ContainSingle();
        result.History[0].Timestamp.Should().Be(exactTimestamp);
    }

    #endregion

    #region Given-When-Then: CorrectlyMapsAllFields

    [Fact]
    public async Task HandleAsync_CorrectlyMapsAllFields_WhenSnapshotExists()
    {
        // Given
        var heatPumpId = HeatPumpId.NewId();
        var from = DateTimeOffset.UtcNow.AddHours(-HoursInDay);
        var to = DateTimeOffset.UtcNow;
        var timestamp = from.AddHours(12);

        var snapshots = new List<HeatPumpSnapshot>
        {
            CreateDetailedTestSnapshot(
                heatPumpId,
                1,
                timestamp,
                isOn: true,
                outsideTemp: OutsideTempCelsius5_5,
                chOutletTemp: ChOutletTempCelsius35,
                dhwActualTemp: DhwActualTempCelsius48,
                compressorFreq: CompressorFrequencyHertz45,
                consumption: PowerConsumptionWatts1200,
                cop: ExpectedCop4_17,
                isDefrosting: false)
        };

        _repository
            .GetHistoryAsync(heatPumpId, from, to, Arg.Any<CancellationToken>())
            .Returns(snapshots);

        // When
        var result = await _handler.HandleAsync(new GetHeatPumpHistory.Query(heatPumpId, from, to));

        // Then
        result.History.Should().ContainSingle();
        var dataPoint = result.History[0];
        dataPoint.Timestamp.Should().Be(timestamp);
        dataPoint.IsOn.Should().BeTrue();
        dataPoint.OutsideTemperatureCelsius.Should().Be(OutsideTempCelsius5_5);
        dataPoint.CH_OutletTemperatureCelsius.Should().Be(ChOutletTempCelsius35);
        dataPoint.DHW_ActualTemperatureCelsius.Should().Be(DhwActualTempCelsius48);
        dataPoint.CompressorFrequencyHertz.Should().Be(CompressorFrequencyHertz45);
        dataPoint.HeatPowerConsumptionWatts.Should().Be(PowerConsumptionWatts1200);
        dataPoint.HeatingCop.Should().Be(ExpectedCop4_17);
        dataPoint.IsDefrosting.Should().BeFalse();
    }

    [Fact]
    public async Task HandleAsync_CorrectlyMapsDefrostState_WhenDefrosting()
    {
        // Given
        var heatPumpId = HeatPumpId.NewId();
        var from = DateTimeOffset.UtcNow.AddHours(-HoursInDay);
        var to = DateTimeOffset.UtcNow;

        var snapshots = new List<HeatPumpSnapshot>
        {
            CreateDetailedTestSnapshot(
                heatPumpId,
                1,
                from.AddHours(1),
                isOn: true,
                outsideTemp: OutsideTempDefrostCelsius,
                chOutletTemp: ChOutletTempDefrostCelsius,
                dhwActualTemp: DhwActualTempCelsius45,
                compressorFreq: CompressorFrequencyHertz0,
                consumption: PowerConsumptionWatts500,
                cop: 0m,
                isDefrosting: true)
        };

        _repository
            .GetHistoryAsync(heatPumpId, from, to, Arg.Any<CancellationToken>())
            .Returns(snapshots);

        // When
        var result = await _handler.HandleAsync(new GetHeatPumpHistory.Query(heatPumpId, from, to));

        // Then
        result.History.Should().ContainSingle();
        result.History[0].IsDefrosting.Should().BeTrue();
    }

    #endregion

    #region Given-When-Then: DateRangeFiltering

    [Fact]
    public async Task HandleAsync_PassesCorrectDateRange_ToRepository()
    {
        // Given
        var heatPumpId = HeatPumpId.NewId();
        var from = new DateTimeOffset(2024, 1, 15, 10, 30, 0, TimeSpan.Zero);
        var to = new DateTimeOffset(2024, 1, 16, 10, 30, 0, TimeSpan.Zero);

        _repository
            .GetHistoryAsync(heatPumpId, from, to, Arg.Any<CancellationToken>())
            .Returns(new List<HeatPumpSnapshot>());

        // When
        await _handler.HandleAsync(new GetHeatPumpHistory.Query(heatPumpId, from, to));

        // Then
        await _repository.Received(1).GetHistoryAsync(heatPumpId, from, to, Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task HandleAsync_PassesCorrectHeatPumpId_ToRepository()
    {
        // Given
        var heatPumpId = HeatPumpId.NewId();
        var from = DateTimeOffset.UtcNow.AddHours(-HoursInDay);
        var to = DateTimeOffset.UtcNow;

        _repository
            .GetHistoryAsync(heatPumpId, from, to, Arg.Any<CancellationToken>())
            .Returns(new List<HeatPumpSnapshot>());

        // When
        await _handler.HandleAsync(new GetHeatPumpHistory.Query(heatPumpId, from, to));

        // Then
        await _repository.Received(1).GetHistoryAsync(heatPumpId, Arg.Any<DateTimeOffset>(), Arg.Any<DateTimeOffset>(), Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task HandleAsync_ReturnsOnlySnapshotsFromRepository_WhenFiltered()
    {
        // Given
        var heatPumpId = HeatPumpId.NewId();
        var from = DateTimeOffset.UtcNow.AddHours(-HoursIn12HourRange); // Last 12 hours only
        var to = DateTimeOffset.UtcNow;

        // Repository returns only 2 snapshots (as if filtered by date)
        var snapshots = new List<HeatPumpSnapshot>
        {
            CreateTestSnapshot(heatPumpId, 1, from.AddHours(2), outsideTemp: OutsideTempCelsius8, isOn: true),
            CreateTestSnapshot(heatPumpId, 2, from.AddHours(6), outsideTemp: OutsideTempCelsius10, isOn: true)
        };

        _repository
            .GetHistoryAsync(heatPumpId, from, to, Arg.Any<CancellationToken>())
            .Returns(snapshots);

        // When
        var result = await _handler.HandleAsync(new GetHeatPumpHistory.Query(heatPumpId, from, to));

        // Then
        result.History.Should().HaveCount(2);
    }

    #endregion

    #region Given-When-Then: MultipleSnapshots

    [Fact]
    public async Task HandleAsync_ReturnsAllSnapshots_WhenLargeDataSet()
    {
        // Given
        var heatPumpId = HeatPumpId.NewId();
        var from = DateTimeOffset.UtcNow.AddDays(-DaysInWeek);
        var to = DateTimeOffset.UtcNow;

        // Create 100 snapshots
        var snapshots = Enumerable.Range(0, LargeDatasetSnapshots)
            .Select(i => CreateTestSnapshot(
                heatPumpId,
                i,
                from.AddHours(i),
                outsideTemp: OutsideTempCelsius5 + (i * 0.1m),
                isOn: i % 2 == 0))
            .ToList();

        _repository
            .GetHistoryAsync(heatPumpId, from, to, Arg.Any<CancellationToken>())
            .Returns(snapshots);

        // When
        var result = await _handler.HandleAsync(new GetHeatPumpHistory.Query(heatPumpId, from, to));

        // Then
        result.History.Should().HaveCount(LargeDatasetSnapshots);
    }

    [Fact]
    public async Task HandleAsync_CorrectlyHandlesMixedOnOffStates_InHistory()
    {
        // Given
        var heatPumpId = HeatPumpId.NewId();
        var from = DateTimeOffset.UtcNow.AddHours(-HoursIn6HourRange);
        var to = DateTimeOffset.UtcNow;

        var snapshots = new List<HeatPumpSnapshot>
        {
            CreateTestSnapshot(heatPumpId, 1, from.AddHours(1), outsideTemp: OutsideTempCelsius5, isOn: true),
            CreateTestSnapshot(heatPumpId, 2, from.AddHours(2), outsideTemp: OutsideTempCelsius6, isOn: false),
            CreateTestSnapshot(heatPumpId, 3, from.AddHours(3), outsideTemp: OutsideTempCelsius7, isOn: true),
            CreateTestSnapshot(heatPumpId, 4, from.AddHours(4), outsideTemp: OutsideTempCelsius8, isOn: false)
        };

        _repository
            .GetHistoryAsync(heatPumpId, from, to, Arg.Any<CancellationToken>())
            .Returns(snapshots);

        // When
        var result = await _handler.HandleAsync(new GetHeatPumpHistory.Query(heatPumpId, from, to));

        // Then
        result.History.Should().HaveCount(4);
        result.History[0].IsOn.Should().BeTrue();
        result.History[1].IsOn.Should().BeFalse();
        result.History[2].IsOn.Should().BeTrue();
        result.History[3].IsOn.Should().BeFalse();
    }

    #endregion

    #region Test Data Builders

    private static HeatPumpSnapshot CreateTestSnapshot(
        HeatPumpId heatPumpId,
        long snapshotId,
        DateTimeOffset timestamp,
        decimal outsideTemp,
        bool isOn)
    {
        return HeatPumpSnapshot.Reconstitute(
            HeatPumpSnapshotId.From(snapshotId),
            heatPumpId,
            timestamp,
            isOn,
            OperatingMode.HeatDhw,
            PumpFlow.FromLitersPerMinute(DefaultPumpFlowLitersPerMinute),
            OutsideTemperature.FromCelsius(outsideTemp),
            new CentralHeatingData(
                WaterTemperature.FromCelsius(ChInletTempCelsius30),
                WaterTemperature.FromCelsius(ChOutletTempCelsius35),
                WaterTemperature.FromCelsius(ChTargetTempCelsius40)),
            new DomesticHotWaterData(
                DhwTemperature.FromCelsius(DhwActualTempCelsius45),
                DhwTemperature.FromCelsius(DhwTargetTempCelsius50)),
            Frequency.FromHertz(CompressorFrequencyHertz40),
            new PowerData(
                Power.FromWatts(PowerProductionWatts4000),
                Power.FromWatts(PowerConsumptionWatts1000),
                Power.Zero,
                Power.Zero,
                Power.Zero,
                Power.Zero),
            new OperationsData(OperationsCompressorHours, OperationsCompressorStarts),
            DefrostData.Inactive,
            ErrorCode.None);
    }

    private static HeatPumpSnapshot CreateDetailedTestSnapshot(
        HeatPumpId heatPumpId,
        long snapshotId,
        DateTimeOffset timestamp,
        bool isOn,
        decimal outsideTemp,
        decimal chOutletTemp,
        decimal dhwActualTemp,
        decimal compressorFreq,
        decimal consumption,
        decimal cop,
        bool isDefrosting)
    {
        // Calculate production from consumption and COP
        var production = cop > 0 ? consumption * cop : 0;

        return HeatPumpSnapshot.Reconstitute(
            HeatPumpSnapshotId.From(snapshotId),
            heatPumpId,
            timestamp,
            isOn,
            OperatingMode.HeatDhw,
            PumpFlow.FromLitersPerMinute(DefaultPumpFlowLitersPerMinute),
            OutsideTemperature.FromCelsius(outsideTemp),
            new CentralHeatingData(
                WaterTemperature.FromCelsius(chOutletTemp - 5.0m),
                WaterTemperature.FromCelsius(chOutletTemp),
                WaterTemperature.FromCelsius(chOutletTemp + 5.0m)),
            new DomesticHotWaterData(
                DhwTemperature.FromCelsius(dhwActualTemp),
                DhwTemperature.FromCelsius(DhwTargetTempCelsius50)),
            Frequency.FromHertz(compressorFreq),
            new PowerData(
                Power.FromWatts(production),
                Power.FromWatts(consumption),
                Power.Zero,
                Power.Zero,
                Power.Zero,
                Power.Zero),
            new OperationsData(OperationsCompressorHours, OperationsCompressorStarts),
            isDefrosting ? DefrostData.Active : DefrostData.Inactive,
            ErrorCode.None);
    }

    #endregion
}
