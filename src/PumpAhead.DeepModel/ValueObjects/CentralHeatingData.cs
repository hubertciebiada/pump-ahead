namespace PumpAhead.DeepModel.ValueObjects;

public readonly record struct CentralHeatingData(
    WaterTemperature InletTemperature,
    WaterTemperature OutletTemperature,
    WaterTemperature TargetTemperature);
