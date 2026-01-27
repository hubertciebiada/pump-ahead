namespace PumpAhead.DeepModel.ValueObjects;

public readonly record struct Frequency : IComparable<Frequency>
{
    public decimal Hertz { get; }

    private Frequency(decimal hertz)
    {
        if (hertz < 0)
            throw new ArgumentOutOfRangeException(nameof(hertz), "Frequency cannot be negative");

        Hertz = hertz;
    }

    public static Frequency FromHertz(decimal hertz) => new(hertz);

    public static bool operator >(Frequency a, Frequency b) => a.Hertz > b.Hertz;
    public static bool operator <(Frequency a, Frequency b) => a.Hertz < b.Hertz;
    public static bool operator >=(Frequency a, Frequency b) => a.Hertz >= b.Hertz;
    public static bool operator <=(Frequency a, Frequency b) => a.Hertz <= b.Hertz;

    public int CompareTo(Frequency other) => Hertz.CompareTo(other.Hertz);

    public override string ToString() =>
        string.Format(System.Globalization.CultureInfo.InvariantCulture, "{0:F1} Hz", Hertz);
}
