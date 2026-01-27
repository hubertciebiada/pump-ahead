namespace PumpAhead.DeepModel.ValueObjects;

public readonly record struct HeatPumpId
{
    public Guid Value { get; }

    private HeatPumpId(Guid value)
    {
        if (value == Guid.Empty)
            throw new ArgumentException("HeatPump ID cannot be empty", nameof(value));

        Value = value;
    }

    public static HeatPumpId From(Guid value) => new(value);

    public static HeatPumpId NewId() => new(Guid.NewGuid());

    public override string ToString() => Value.ToString();
}
