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
    public CompressorData Compressor { get; private set; }

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
        CompressorData compressor)
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
        Compressor = compressor;
    }

    public void SyncFrom(
        bool isOn,
        OperatingMode operatingMode,
        PumpFlow pumpFlow,
        OutsideTemperature outsideTemperature,
        CentralHeatingData centralHeating,
        DomesticHotWaterData domesticHotWater,
        CompressorData compressor)
    {
        IsOn = isOn;
        OperatingMode = operatingMode;
        PumpFlow = pumpFlow;
        OutsideTemperature = outsideTemperature;
        CentralHeating = centralHeating;
        DomesticHotWater = domesticHotWater;
        Compressor = compressor;
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
        CompressorData compressor)
    {
        return new HeatPump(
            id, model, lastSyncTime, isOn, operatingMode, pumpFlow,
            outsideTemperature, centralHeating, domesticHotWater, compressor);
    }
}
