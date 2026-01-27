namespace PumpAhead.DeepModel.ValueObjects;

/// <summary>
/// Domestic hot water data from the heat pump.
/// Maps to Heishamon: TOP9 (Target), TOP10 (Actual).
/// </summary>
public readonly record struct DomesticHotWaterData
{
    /// <summary>TOP10: DHW_Temp — actual tank temperature.</summary>
    public DhwTemperature ActualTemperature { get; }

    /// <summary>TOP9: DHW_Target_Temp — target tank temperature.</summary>
    public DhwTemperature TargetTemperature { get; }

    private DomesticHotWaterData(
        DhwTemperature actualTemperature,
        DhwTemperature targetTemperature)
    {
        ActualTemperature = actualTemperature;
        TargetTemperature = targetTemperature;
    }

    public static DomesticHotWaterData Create(
        DhwTemperature actualTemperature,
        DhwTemperature targetTemperature) =>
        new(actualTemperature, targetTemperature);
}
