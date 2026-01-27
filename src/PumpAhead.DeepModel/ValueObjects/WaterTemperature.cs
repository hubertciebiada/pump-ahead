namespace PumpAhead.DeepModel.ValueObjects;

/// <summary>
/// Water temperature as reported by the heat pump (inlet, outlet, or target).
/// No restrictive range — values come directly from Heishamon (TOP5, TOP6, TOP7).
/// </summary>
public readonly record struct WaterTemperature : IComparable<WaterTemperature>
{
    public decimal Celsius { get; }

    private WaterTemperature(decimal celsius)
    {
        Celsius = celsius;
    }

    public static WaterTemperature FromCelsius(decimal celsius) => new(celsius);

    public static bool operator >(WaterTemperature a, WaterTemperature b) => a.Celsius > b.Celsius;
    public static bool operator <(WaterTemperature a, WaterTemperature b) => a.Celsius < b.Celsius;
    public static bool operator >=(WaterTemperature a, WaterTemperature b) => a.Celsius >= b.Celsius;
    public static bool operator <=(WaterTemperature a, WaterTemperature b) => a.Celsius <= b.Celsius;

    public int CompareTo(WaterTemperature other) => Celsius.CompareTo(other.Celsius);

    public override string ToString() =>
        string.Format(System.Globalization.CultureInfo.InvariantCulture, "{0:F1}°C", Celsius);
}
