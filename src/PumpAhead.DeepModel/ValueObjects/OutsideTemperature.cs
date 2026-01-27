namespace PumpAhead.DeepModel.ValueObjects;

/// <summary>
/// Outside ambient temperature as reported by the heat pump.
/// Heishamon TOP14: Outside_Temp.
/// </summary>
public readonly record struct OutsideTemperature : IComparable<OutsideTemperature>
{
    public decimal Celsius { get; }

    private OutsideTemperature(decimal celsius)
    {
        Celsius = celsius;
    }

    public static OutsideTemperature FromCelsius(decimal celsius) => new(celsius);

    public static bool operator >(OutsideTemperature a, OutsideTemperature b) => a.Celsius > b.Celsius;
    public static bool operator <(OutsideTemperature a, OutsideTemperature b) => a.Celsius < b.Celsius;
    public static bool operator >=(OutsideTemperature a, OutsideTemperature b) => a.Celsius >= b.Celsius;
    public static bool operator <=(OutsideTemperature a, OutsideTemperature b) => a.Celsius <= b.Celsius;

    public int CompareTo(OutsideTemperature other) => Celsius.CompareTo(other.Celsius);

    public override string ToString() =>
        string.Format(System.Globalization.CultureInfo.InvariantCulture, "{0:F1}°C", Celsius);
}
