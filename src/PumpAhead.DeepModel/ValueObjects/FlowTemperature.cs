namespace PumpAhead.DeepModel.ValueObjects;

public readonly record struct FlowTemperature : IComparable<FlowTemperature>
{
    private const decimal MinValue = 20m;
    private const decimal MaxValue = 35m;

    public decimal Celsius { get; }

    private FlowTemperature(decimal celsius)
    {
        if (celsius < MinValue || celsius > MaxValue)
            throw new ArgumentOutOfRangeException(
                nameof(celsius),
                $"Flow temperature must be between {MinValue}°C and {MaxValue}°C");

        Celsius = celsius;
    }

    public static FlowTemperature FromCelsius(decimal celsius) => new(celsius);

    public static bool operator >(FlowTemperature a, FlowTemperature b) => a.Celsius > b.Celsius;
    public static bool operator <(FlowTemperature a, FlowTemperature b) => a.Celsius < b.Celsius;
    public static bool operator >=(FlowTemperature a, FlowTemperature b) => a.Celsius >= b.Celsius;
    public static bool operator <=(FlowTemperature a, FlowTemperature b) => a.Celsius <= b.Celsius;

    public int CompareTo(FlowTemperature other) => Celsius.CompareTo(other.Celsius);

    public override string ToString() =>
        string.Format(System.Globalization.CultureInfo.InvariantCulture, "{0:F1}°C", Celsius);
}
