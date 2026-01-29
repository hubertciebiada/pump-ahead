namespace PumpAhead.DeepModel.ValueObjects;

public readonly record struct DomesticHotWaterData(
    DhwTemperature ActualTemperature,
    DhwTemperature TargetTemperature);
