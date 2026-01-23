namespace PumpAhead.DeepModel.ValueObjects;

public readonly record struct Temperature : IComparable<Temperature>
{
    public decimal Celsius { get; }

    private Temperature(decimal celsius)
    {
        Celsius = celsius;
    }

    public static Temperature FromCelsius(decimal celsius) => new(celsius);

    public static Temperature operator +(Temperature a, Temperature b) =>
        new(a.Celsius + b.Celsius);

    public static Temperature operator -(Temperature a, Temperature b) =>
        new(a.Celsius - b.Celsius);

    public static bool operator >(Temperature a, Temperature b) =>
        a.Celsius > b.Celsius;

    public static bool operator <(Temperature a, Temperature b) =>
        a.Celsius < b.Celsius;

    public static bool operator >=(Temperature a, Temperature b) =>
        a.Celsius >= b.Celsius;

    public static bool operator <=(Temperature a, Temperature b) =>
        a.Celsius <= b.Celsius;

    public int CompareTo(Temperature other) => Celsius.CompareTo(other.Celsius);

    public Temperature Clamp(Temperature min, Temperature max)
    {
        if (this < min) return min;
        if (this > max) return max;
        return this;
    }

    public override string ToString() => string.Format(System.Globalization.CultureInfo.InvariantCulture, "{0:F1}°C", Celsius);
}
