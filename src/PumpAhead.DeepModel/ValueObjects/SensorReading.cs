namespace PumpAhead.DeepModel.ValueObjects;

public readonly record struct SensorReading(
    SensorId SensorId,
    Temperature Temperature,
    DateTimeOffset Timestamp);
