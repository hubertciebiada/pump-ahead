using PumpAhead.DeepModel;
using PumpAhead.DeepModel.Entities;
using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.Tests.Common.Builders;

/// <summary>
/// Test Data Builder for HeatPumpSnapshot entity.
/// Follows Object Mother / Test Data Builder pattern.
/// </summary>
public sealed class HeatPumpSnapshotBuilder
{
    private HeatPumpSnapshotId _id = HeatPumpSnapshotId.From(0);
    private HeatPumpId _heatPumpId = HeatPumpId.NewId();
    private DateTimeOffset _timestamp = DateTimeOffset.UtcNow;
    private bool _isOn = true;
    private OperatingMode _operatingMode = OperatingMode.HeatDhw;
    private PumpFlow _pumpFlow = PumpFlow.FromLitersPerMinute(12.5m);
    private OutsideTemperature _outsideTemperature = OutsideTemperature.FromCelsius(5.0m);
    private CentralHeatingData _centralHeating = new(
        WaterTemperature.FromCelsius(35.0m),
        WaterTemperature.FromCelsius(30.0m),
        WaterTemperature.FromCelsius(38.0m));
    private DomesticHotWaterData _domesticHotWater = new(
        DhwTemperature.FromCelsius(48.0m),
        DhwTemperature.FromCelsius(50.0m));
    private Frequency _compressorFrequency = Frequency.FromHertz(45.0m);
    private PowerData _power = new(
        Power.FromWatts(3500),
        Power.FromWatts(1000),
        Power.Zero,
        Power.Zero,
        Power.Zero,
        Power.Zero);
    private OperationsData _operations = new(1500, 250);
    private DefrostData _defrost = DefrostData.Inactive;
    private ErrorCode _errorCode = ErrorCode.None;

    /// <summary>
    /// Creates a new builder with default valid values.
    /// </summary>
    public static HeatPumpSnapshotBuilder Valid() => new();

    /// <summary>
    /// Creates a builder from an existing HeatPump state.
    /// </summary>
    public static HeatPumpSnapshotBuilder FromHeatPump(HeatPumpBuilder heatPumpBuilder)
    {
        var heatPump = heatPumpBuilder.Build();
        return FromHeatPump(heatPump);
    }

    /// <summary>
    /// Creates a builder from an existing HeatPump state.
    /// </summary>
    public static HeatPumpSnapshotBuilder FromHeatPump(
        PumpAhead.DeepModel.Aggregates.HeatPump heatPump,
        DateTimeOffset? timestamp = null)
    {
        return new HeatPumpSnapshotBuilder()
            .WithHeatPumpId(heatPump.Id)
            .WithTimestamp(timestamp ?? heatPump.LastSyncTime)
            .WithIsOn(heatPump.IsOn)
            .WithOperatingMode(heatPump.OperatingMode)
            .WithPumpFlow(heatPump.PumpFlow)
            .WithOutsideTemperature(heatPump.OutsideTemperature)
            .WithCentralHeating(heatPump.CentralHeating)
            .WithDomesticHotWater(heatPump.DomesticHotWater)
            .WithCompressorFrequency(heatPump.CompressorFrequency)
            .WithPower(heatPump.Power)
            .WithOperations(heatPump.Operations)
            .WithDefrost(heatPump.Defrost)
            .WithErrorCode(heatPump.ErrorCode);
    }

    /// <summary>
    /// Creates a series of snapshots with incrementing timestamps.
    /// </summary>
    public static IEnumerable<HeatPumpSnapshot> CreateSeries(
        HeatPumpId heatPumpId,
        int count,
        TimeSpan interval,
        DateTimeOffset? startTime = null)
    {
        var time = startTime ?? DateTimeOffset.UtcNow.AddMinutes(-count * interval.TotalMinutes);

        for (int i = 0; i < count; i++)
        {
            yield return new HeatPumpSnapshotBuilder()
                .WithHeatPumpId(heatPumpId)
                .WithTimestamp(time)
                .WithOutsideTemperature(OutsideTemperature.FromCelsius(5.0m + (i % 10)))
                .Build();

            time = time.Add(interval);
        }
    }

    public HeatPumpSnapshotBuilder WithId(HeatPumpSnapshotId id)
    {
        _id = id;
        return this;
    }

    public HeatPumpSnapshotBuilder WithId(long id) => WithId(HeatPumpSnapshotId.From(id));

    public HeatPumpSnapshotBuilder WithHeatPumpId(HeatPumpId heatPumpId)
    {
        _heatPumpId = heatPumpId;
        return this;
    }

    public HeatPumpSnapshotBuilder WithHeatPumpId(Guid id) => WithHeatPumpId(HeatPumpId.From(id));

    public HeatPumpSnapshotBuilder WithTimestamp(DateTimeOffset timestamp)
    {
        _timestamp = timestamp;
        return this;
    }

    public HeatPumpSnapshotBuilder WithIsOn(bool isOn)
    {
        _isOn = isOn;
        return this;
    }

    public HeatPumpSnapshotBuilder WithOperatingMode(OperatingMode operatingMode)
    {
        _operatingMode = operatingMode;
        return this;
    }

    public HeatPumpSnapshotBuilder WithPumpFlow(PumpFlow pumpFlow)
    {
        _pumpFlow = pumpFlow;
        return this;
    }

    public HeatPumpSnapshotBuilder WithPumpFlow(decimal litersPerMinute) =>
        WithPumpFlow(PumpFlow.FromLitersPerMinute(litersPerMinute));

    public HeatPumpSnapshotBuilder WithOutsideTemperature(OutsideTemperature outsideTemperature)
    {
        _outsideTemperature = outsideTemperature;
        return this;
    }

    public HeatPumpSnapshotBuilder WithOutsideTemperature(decimal celsius) =>
        WithOutsideTemperature(OutsideTemperature.FromCelsius(celsius));

    public HeatPumpSnapshotBuilder WithCentralHeating(CentralHeatingData centralHeating)
    {
        _centralHeating = centralHeating;
        return this;
    }

    public HeatPumpSnapshotBuilder WithCentralHeating(decimal inlet, decimal outlet, decimal target) =>
        WithCentralHeating(new CentralHeatingData(
            WaterTemperature.FromCelsius(inlet),
            WaterTemperature.FromCelsius(outlet),
            WaterTemperature.FromCelsius(target)));

    public HeatPumpSnapshotBuilder WithDomesticHotWater(DomesticHotWaterData domesticHotWater)
    {
        _domesticHotWater = domesticHotWater;
        return this;
    }

    public HeatPumpSnapshotBuilder WithDomesticHotWater(decimal actual, decimal target) =>
        WithDomesticHotWater(new DomesticHotWaterData(
            DhwTemperature.FromCelsius(actual),
            DhwTemperature.FromCelsius(target)));

    public HeatPumpSnapshotBuilder WithCompressorFrequency(Frequency compressorFrequency)
    {
        _compressorFrequency = compressorFrequency;
        return this;
    }

    public HeatPumpSnapshotBuilder WithCompressorFrequency(decimal hertz) =>
        WithCompressorFrequency(Frequency.FromHertz(hertz));

    public HeatPumpSnapshotBuilder WithPower(PowerData power)
    {
        _power = power;
        return this;
    }

    public HeatPumpSnapshotBuilder WithHeatingPower(decimal production, decimal consumption) =>
        WithPower(new PowerData(
            Power.FromWatts(production),
            Power.FromWatts(consumption),
            _power.CoolProduction,
            _power.CoolConsumption,
            _power.DhwProduction,
            _power.DhwConsumption));

    public HeatPumpSnapshotBuilder WithOperations(OperationsData operations)
    {
        _operations = operations;
        return this;
    }

    public HeatPumpSnapshotBuilder WithOperations(decimal hours, int starts) =>
        WithOperations(new OperationsData(hours, starts));

    public HeatPumpSnapshotBuilder WithDefrost(DefrostData defrost)
    {
        _defrost = defrost;
        return this;
    }

    public HeatPumpSnapshotBuilder WithErrorCode(ErrorCode errorCode)
    {
        _errorCode = errorCode;
        return this;
    }

    /// <summary>
    /// Builds the HeatPumpSnapshot using the CreateFrom factory method.
    /// </summary>
    public HeatPumpSnapshot Build()
    {
        return HeatPumpSnapshot.CreateFrom(
            _heatPumpId,
            _timestamp,
            _isOn,
            _operatingMode,
            _pumpFlow,
            _outsideTemperature,
            _centralHeating,
            _domesticHotWater,
            _compressorFrequency,
            _power,
            _operations,
            _defrost,
            _errorCode);
    }

    /// <summary>
    /// Builds the HeatPumpSnapshot using Reconstitute (for persistence tests with specific IDs).
    /// </summary>
    public HeatPumpSnapshot BuildReconstituted()
    {
        return HeatPumpSnapshot.Reconstitute(
            _id,
            _heatPumpId,
            _timestamp,
            _isOn,
            _operatingMode,
            _pumpFlow,
            _outsideTemperature,
            _centralHeating,
            _domesticHotWater,
            _compressorFrequency,
            _power,
            _operations,
            _defrost,
            _errorCode);
    }

    /// <summary>
    /// Implicit conversion to HeatPumpSnapshot for convenient usage in tests.
    /// </summary>
    public static implicit operator HeatPumpSnapshot(HeatPumpSnapshotBuilder builder) => builder.Build();
}
