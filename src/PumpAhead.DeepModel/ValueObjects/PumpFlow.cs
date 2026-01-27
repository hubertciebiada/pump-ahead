namespace PumpAhead.DeepModel.ValueObjects;

/// <summary>
/// Water pump flow rate in liters per minute.
/// Heishamon TOP1: Pump_Flow.
/// </summary>
public readonly record struct PumpFlow : IComparable<PumpFlow>
{
    public decimal LitersPerMinute { get; }

    private PumpFlow(decimal litersPerMinute)
    {
        if (litersPerMinute < 0)
            throw new ArgumentOutOfRangeException(nameof(litersPerMinute), "Pump flow cannot be negative");

        LitersPerMinute = litersPerMinute;
    }

    public static PumpFlow FromLitersPerMinute(decimal litersPerMinute) => new(litersPerMinute);

    public static bool operator >(PumpFlow a, PumpFlow b) => a.LitersPerMinute > b.LitersPerMinute;
    public static bool operator <(PumpFlow a, PumpFlow b) => a.LitersPerMinute < b.LitersPerMinute;
    public static bool operator >=(PumpFlow a, PumpFlow b) => a.LitersPerMinute >= b.LitersPerMinute;
    public static bool operator <=(PumpFlow a, PumpFlow b) => a.LitersPerMinute <= b.LitersPerMinute;

    public int CompareTo(PumpFlow other) => LitersPerMinute.CompareTo(other.LitersPerMinute);

    public override string ToString() =>
        string.Format(System.Globalization.CultureInfo.InvariantCulture, "{0:F1} l/min", LitersPerMinute);
}
