namespace PumpAhead.DeepModel.ValueObjects;

public readonly record struct SensorId
{
    public Guid Value { get; }

    private SensorId(Guid value)
    {
        Value = value;
    }

    public static SensorId From(Guid value) => new(value);
    public static SensorId New() => new(Guid.NewGuid());

    public override string ToString() => Value.ToString();
}
