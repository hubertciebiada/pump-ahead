namespace PumpAhead.DeepModel.ValueObjects;

public readonly record struct SensorId
{
    public string Value { get; }

    private SensorId(string value)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(value);
        Value = value;
    }

    public static SensorId From(string value) => new(value);

    public override string ToString() => Value;
}
