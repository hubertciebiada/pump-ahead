namespace PumpAhead.DeepModel.ValueObjects;

/// <summary>
/// Domestic hot water temperature as reported by the heat pump.
/// Heishamon TOP9 (target) and TOP10 (actual).
/// No restrictive range — actual tank temperature can be any value.
/// </summary>
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
