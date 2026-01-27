namespace PumpAhead.DeepModel.ValueObjects;

/// <summary>
/// Central heating water circuit data from the heat pump.
/// Maps to Heishamon: TOP5 (Inlet), TOP6 (Outlet), TOP7 (Target).
/// </summary>
public readonly record struct CentralHeatingData
{
    /// <summary>TOP5: Main_Inlet_Temp — water returning to the heat pump.</summary>
    public WaterTemperature InletTemperature { get; }

    /// <summary>TOP6: Main_Outlet_Temp — water leaving the heat pump.</summary>
    public WaterTemperature OutletTemperature { get; }

    /// <summary>TOP7: Main_Target_Temp — target outlet temperature.</summary>
    public WaterTemperature TargetTemperature { get; }

    private CentralHeatingData(
        WaterTemperature inletTemperature,
        WaterTemperature outletTemperature,
        WaterTemperature targetTemperature)
    {
        InletTemperature = inletTemperature;
        OutletTemperature = outletTemperature;
        TargetTemperature = targetTemperature;
    }

    public static CentralHeatingData Create(
        WaterTemperature inletTemperature,
        WaterTemperature outletTemperature,
        WaterTemperature targetTemperature) =>
        new(inletTemperature, outletTemperature, targetTemperature);
}
