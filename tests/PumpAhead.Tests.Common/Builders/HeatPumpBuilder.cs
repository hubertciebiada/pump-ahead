using PumpAhead.DeepModel;
using PumpAhead.DeepModel.Aggregates;
using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.Tests.Common.Builders;

/// <summary>
/// Test Data Builder for HeatPump aggregate.
/// Follows Object Mother / Test Data Builder pattern.
/// </summary>
public sealed class HeatPumpBuilder
{
    private HeatPumpId _id = HeatPumpId.NewId();
    private string _model = "Panasonic WH-MDC09J3E5";
    private DateTimeOffset _lastSyncTime = DateTimeOffset.UtcNow;
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
    public static HeatPumpBuilder Valid() => new();

    /// <summary>
    /// Creates a builder for a heat pump that is turned off.
    /// </summary>
    public static HeatPumpBuilder TurnedOff() => new HeatPumpBuilder()
        .WithIsOn(false)
        .WithCompressorFrequency(Frequency.FromHertz(0))
        .WithPower(PowerData.Zero);

    /// <summary>
    /// Creates a builder for a heat pump in defrost mode.
    /// </summary>
    public static HeatPumpBuilder Defrosting() => new HeatPumpBuilder()
        .WithDefrost(DefrostData.Active)
        .WithOutsideTemperature(OutsideTemperature.FromCelsius(-5.0m));

    /// <summary>
    /// Creates a builder for a heat pump with an error.
    /// </summary>
    public static HeatPumpBuilder WithError(string errorCode = "H15") => new HeatPumpBuilder()
        .WithErrorCode(ErrorCode.From(errorCode))
        .WithIsOn(false);

    public HeatPumpBuilder WithId(HeatPumpId id)
    {
        _id = id;
        return this;
    }

    public HeatPumpBuilder WithId(Guid id) => WithId(HeatPumpId.From(id));

    public HeatPumpBuilder WithModel(string model)
    {
        _model = model;
        return this;
    }

    public HeatPumpBuilder WithLastSyncTime(DateTimeOffset lastSyncTime)
    {
        _lastSyncTime = lastSyncTime;
        return this;
    }

    public HeatPumpBuilder WithIsOn(bool isOn)
    {
        _isOn = isOn;
        return this;
    }

    public HeatPumpBuilder WithOperatingMode(OperatingMode operatingMode)
    {
        _operatingMode = operatingMode;
        return this;
    }

    public HeatPumpBuilder WithPumpFlow(PumpFlow pumpFlow)
    {
        _pumpFlow = pumpFlow;
        return this;
    }

    public HeatPumpBuilder WithPumpFlow(decimal litersPerMinute) =>
        WithPumpFlow(PumpFlow.FromLitersPerMinute(litersPerMinute));

    public HeatPumpBuilder WithOutsideTemperature(OutsideTemperature outsideTemperature)
    {
        _outsideTemperature = outsideTemperature;
        return this;
    }

    public HeatPumpBuilder WithOutsideTemperature(decimal celsius) =>
        WithOutsideTemperature(OutsideTemperature.FromCelsius(celsius));

    public HeatPumpBuilder WithCentralHeating(CentralHeatingData centralHeating)
    {
        _centralHeating = centralHeating;
        return this;
    }

    public HeatPumpBuilder WithCentralHeating(decimal inlet, decimal outlet, decimal target) =>
        WithCentralHeating(new CentralHeatingData(
            WaterTemperature.FromCelsius(inlet),
            WaterTemperature.FromCelsius(outlet),
            WaterTemperature.FromCelsius(target)));

    public HeatPumpBuilder WithDomesticHotWater(DomesticHotWaterData domesticHotWater)
    {
        _domesticHotWater = domesticHotWater;
        return this;
    }

    public HeatPumpBuilder WithDomesticHotWater(decimal actual, decimal target) =>
        WithDomesticHotWater(new DomesticHotWaterData(
            DhwTemperature.FromCelsius(actual),
            DhwTemperature.FromCelsius(target)));

    public HeatPumpBuilder WithCompressorFrequency(Frequency compressorFrequency)
    {
        _compressorFrequency = compressorFrequency;
        return this;
    }

    public HeatPumpBuilder WithCompressorFrequency(decimal hertz) =>
        WithCompressorFrequency(Frequency.FromHertz(hertz));

    public HeatPumpBuilder WithPower(PowerData power)
    {
        _power = power;
        return this;
    }

    public HeatPumpBuilder WithHeatingPower(decimal production, decimal consumption) =>
        WithPower(new PowerData(
            Power.FromWatts(production),
            Power.FromWatts(consumption),
            _power.CoolProduction,
            _power.CoolConsumption,
            _power.DhwProduction,
            _power.DhwConsumption));

    public HeatPumpBuilder WithOperations(OperationsData operations)
    {
        _operations = operations;
        return this;
    }

    public HeatPumpBuilder WithOperations(decimal hours, int starts) =>
        WithOperations(new OperationsData(hours, starts));

    public HeatPumpBuilder WithDefrost(DefrostData defrost)
    {
        _defrost = defrost;
        return this;
    }

    public HeatPumpBuilder WithErrorCode(ErrorCode errorCode)
    {
        _errorCode = errorCode;
        return this;
    }

    /// <summary>
    /// Builds the HeatPump aggregate using the Reconstitute factory method.
    /// </summary>
    public HeatPump Build()
    {
        return HeatPump.Reconstitute(
            _id,
            _model,
            _lastSyncTime,
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
    /// Implicit conversion to HeatPump for convenient usage in tests.
    /// </summary>
    public static implicit operator HeatPump(HeatPumpBuilder builder) => builder.Build();
}
