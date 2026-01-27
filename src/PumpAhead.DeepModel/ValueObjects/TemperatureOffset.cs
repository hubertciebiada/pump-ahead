namespace PumpAhead.DeepModel.ValueObjects;

public readonly record struct TemperatureOffset : IComparable<TemperatureOffset>
{
    private const decimal MinValue = -5m;
    private const decimal MaxValue = 5m;

    public decimal Celsius { get; }

    private TemperatureOffset(decimal celsius)
    {
        if (celsius < MinValue || celsius > MaxValue)
            throw new ArgumentOutOfRangeException(
                nameof(celsius),
                $"Temperature offset must be between {MinValue}°C and {MaxValue}°C");

        Celsius = celsius;
    }

    public static TemperatureOffset FromCelsius(decimal celsius) => new(celsius);


    public static bool operator >(TemperatureOffset a, TemperatureOffset b) => a.Celsius > b.Celsius;
    public static bool operator <(TemperatureOffset a, TemperatureOffset b) => a.Celsius < b.Celsius;
    public static bool operator >=(TemperatureOffset a, TemperatureOffset b) => a.Celsius >= b.Celsius;
    public static bool operator <=(TemperatureOffset a, TemperatureOffset b) => a.Celsius <= b.Celsius;

    public int CompareTo(TemperatureOffset other) => Celsius.CompareTo(other.Celsius);

    public override string ToString() =>
        string.Format(System.Globalization.CultureInfo.InvariantCulture, "{0:+0.0;-0.0;0}°C", Celsius);
}
