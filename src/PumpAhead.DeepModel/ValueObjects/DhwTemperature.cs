namespace PumpAhead.DeepModel.ValueObjects;

public readonly record struct DhwTemperature : IComparable<DhwTemperature>
{
    public decimal Celsius { get; }

    private DhwTemperature(decimal celsius)
    {
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
