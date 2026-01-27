namespace PumpAhead.DeepModel.ValueObjects;

public readonly record struct ReturnTemperature : IComparable<ReturnTemperature>
{
    public decimal Celsius { get; }

    private ReturnTemperature(decimal celsius)
    {
        Celsius = celsius;
    }

    public static ReturnTemperature FromCelsius(decimal celsius) => new(celsius);

    public static bool operator >(ReturnTemperature a, ReturnTemperature b) => a.Celsius > b.Celsius;
    public static bool operator <(ReturnTemperature a, ReturnTemperature b) => a.Celsius < b.Celsius;
    public static bool operator >=(ReturnTemperature a, ReturnTemperature b) => a.Celsius >= b.Celsius;
    public static bool operator <=(ReturnTemperature a, ReturnTemperature b) => a.Celsius <= b.Celsius;

    public int CompareTo(ReturnTemperature other) => Celsius.CompareTo(other.Celsius);

    public override string ToString() =>
        string.Format(System.Globalization.CultureInfo.InvariantCulture, "{0:F1}°C", Celsius);
}
