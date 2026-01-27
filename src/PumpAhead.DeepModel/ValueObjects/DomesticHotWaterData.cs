namespace PumpAhead.DeepModel.ValueObjects;

public readonly record struct DomesticHotWaterData
{
    public DhwTemperature ActualTemperature { get; }
    public DhwTemperature TargetTemperature { get; }
    public TemperatureOffset Delta { get; }

    private DomesticHotWaterData(
        DhwTemperature actualTemperature,
        DhwTemperature targetTemperature,
        TemperatureOffset delta)
    {
        ActualTemperature = actualTemperature;
        TargetTemperature = targetTemperature;
        Delta = delta;
    }

    public static DomesticHotWaterData Create(
        DhwTemperature actualTemperature,
        DhwTemperature targetTemperature,
        TemperatureOffset delta) =>
        new(actualTemperature, targetTemperature, delta);
}
