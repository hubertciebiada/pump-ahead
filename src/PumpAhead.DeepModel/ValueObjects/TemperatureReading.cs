namespace PumpAhead.DeepModel.ValueObjects;

public readonly record struct TemperatureReading(
    SensorId SensorId,
    Temperature Temperature,
    DateTimeOffset Timestamp);
