namespace PumpAhead.DeepModel.ValueObjects;

public readonly record struct Frequency
{
    public decimal Hertz { get; }

    private Frequency(decimal hertz)
    {
        if (hertz < 0)
            throw new ArgumentOutOfRangeException(nameof(hertz), "Frequency cannot be negative");

        Hertz = hertz;
    }

    public static Frequency FromHertz(decimal hertz) => new(hertz);

    public override string ToString() =>
        string.Format(System.Globalization.CultureInfo.InvariantCulture, "{0:F1} Hz", Hertz);
}
