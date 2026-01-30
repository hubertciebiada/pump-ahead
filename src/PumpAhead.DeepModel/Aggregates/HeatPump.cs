using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.DeepModel.Aggregates;

public class HeatPump
{
    public HeatPumpId Id { get; private set; }
    public string Model { get; private set; }
    public DateTimeOffset LastSyncTime { get; private set; }

    /// <summary>TOP0: Heatpump_State (on/off).</summary>
    public bool IsOn { get; private set; }

    /// <summary>TOP4: Operating_Mode_State.</summary>
    public OperatingMode OperatingMode { get; private set; }

    /// <summary>TOP1: Pump_Flow (l/min).</summary>
    public PumpFlow PumpFlow { get; private set; }

    /// <summary>TOP14: Outside_Temp.</summary>
    public OutsideTemperature OutsideTemperature { get; private set; }

    /// <summary>TOP5, TOP6, TOP7: Inlet, Outlet, Target water temperatures.</summary>
    public CentralHeatingData CentralHeating { get; private set; }

    /// <summary>TOP9, TOP10: DHW target and actual temperatures.</summary>
    public DomesticHotWaterData DomesticHotWater { get; private set; }

    /// <summary>TOP8: Compressor_Freq.</summary>
    public Frequency CompressorFrequency { get; private set; }

    /// <summary>TOP15-TOP18: Power production and consumption.</summary>
    public PowerData Power { get; private set; }

    /// <summary>TOP11, TOP12: Operations hours and counter.</summary>
    public OperationsData Operations { get; private set; }

    /// <summary>TOP26: Defrosting state.</summary>
    public DefrostData Defrost { get; private set; }

    /// <summary>TOP44: Error code.</summary>
    public ErrorCode ErrorCode { get; private set; }

    private HeatPump(
        HeatPumpId id,
        string model,
        DateTimeOffset lastSyncTime,
        bool isOn,
        OperatingMode operatingMode,
        PumpFlow pumpFlow,
        OutsideTemperature outsideTemperature,
        CentralHeatingData centralHeating,
        DomesticHotWaterData domesticHotWater,
        Frequency compressorFrequency,
        PowerData power,
        OperationsData operations,
        DefrostData defrost,
        ErrorCode errorCode)
    {
        if (string.IsNullOrWhiteSpace(model))
            throw new ArgumentException("Model cannot be empty", nameof(model));

        Id = id;
        Model = model;
        LastSyncTime = lastSyncTime;
        IsOn = isOn;
        OperatingMode = operatingMode;
        PumpFlow = pumpFlow;
        OutsideTemperature = outsideTemperature;
        CentralHeating = centralHeating;
        DomesticHotWater = domesticHotWater;
        CompressorFrequency = compressorFrequency;
        Power = power;
        Operations = operations;
        Defrost = defrost;
        ErrorCode = errorCode;
    }

    public void SyncFrom(
        bool isOn,
        OperatingMode operatingMode,
        PumpFlow pumpFlow,
        OutsideTemperature outsideTemperature,
        CentralHeatingData centralHeating,
        DomesticHotWaterData domesticHotWater,
        Frequency compressorFrequency,
        PowerData power,
        OperationsData operations,
        DefrostData defrost,
        ErrorCode errorCode)
    {
        IsOn = isOn;
        OperatingMode = operatingMode;
        PumpFlow = pumpFlow;
        OutsideTemperature = outsideTemperature;
        CentralHeating = centralHeating;
        DomesticHotWater = domesticHotWater;
        CompressorFrequency = compressorFrequency;
        Power = power;
        Operations = operations;
        Defrost = defrost;
        ErrorCode = errorCode;
        LastSyncTime = DateTimeOffset.UtcNow;
    }

    public static HeatPump Reconstitute(
        HeatPumpId id,
        string model,
        DateTimeOffset lastSyncTime,
        bool isOn,
        OperatingMode operatingMode,
        PumpFlow pumpFlow,
        OutsideTemperature outsideTemperature,
        CentralHeatingData centralHeating,
        DomesticHotWaterData domesticHotWater,
        Frequency compressorFrequency,
        PowerData power,
        OperationsData operations,
        DefrostData defrost,
        ErrorCode errorCode)
    {
        return new HeatPump(
            id, model, lastSyncTime, isOn, operatingMode, pumpFlow,
            outsideTemperature, centralHeating, domesticHotWater, compressorFrequency,
            power, operations, defrost, errorCode);
    }
}
