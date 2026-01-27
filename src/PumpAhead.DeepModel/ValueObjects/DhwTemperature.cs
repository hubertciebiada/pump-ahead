namespace PumpAhead.DeepModel.ValueObjects;

public readonly record struct DhwTemperature : IComparable<DhwTemperature>
{
    private const decimal MinValue = 40m;
    private const decimal MaxValue = 60m;

    public decimal Celsius { get; }

    private DhwTemperature(decimal celsius)
    {
        if (celsius < MinValue || celsius > MaxValue)
            throw new ArgumentOutOfRangeException(
                nameof(celsius),
                $"DHW temperature must be between {MinValue}°C and {MaxValue}°C");

        Celsius = celsius;
    }

    public static DhwTemperature FromCelsius(decimal celsius) => new(celsius);

    public static bool operator >(DhwTemperature a, DhwTemperature b) => a.Celsius > b.Celsius;
    public static bool operator <(DhwTemperature a, DhwTemperature b) => a.Celsius < b.Celsius;
    public static bool operator >=(DhwTemperature a, DhwTemperature b) => a.Celsius >= b.Celsius;
    public static bool operator <=(DhwTemperature a, DhwTemperature b) => a.Celsius <= b.Celsius;

    public int CompareTo(DhwTemperature other) => Celsius.CompareTo(other.Celsius);

    public override string ToString() =>
        string.Format(System.Globalization.CultureInfo.InvariantCulture, "{0:F1}°C", Celsius);
}
