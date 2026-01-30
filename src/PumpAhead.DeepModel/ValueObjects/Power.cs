namespace PumpAhead.DeepModel.ValueObjects;

/// <summary>
/// Electrical power in watts.
/// HeishaMon TOP15-TOP18: Heat/Cool/DHW Power Production/Consumption.
/// </summary>
public readonly record struct Power : IComparable<Power>
{
    public decimal Watts { get; }

    private Power(decimal watts)
    {
        if (watts < 0)
            throw new ArgumentOutOfRangeException(nameof(watts), "Power cannot be negative");

        Watts = watts;
    }

    public static Power FromWatts(decimal watts) => new(watts);

    public static Power Zero => new(0);

    public decimal Kilowatts => Watts / 1000m;

    public static Power operator +(Power a, Power b) => new(a.Watts + b.Watts);

    public static bool operator >(Power a, Power b) => a.Watts > b.Watts;
    public static bool operator <(Power a, Power b) => a.Watts < b.Watts;
    public static bool operator >=(Power a, Power b) => a.Watts >= b.Watts;
    public static bool operator <=(Power a, Power b) => a.Watts <= b.Watts;

    public int CompareTo(Power other) => Watts.CompareTo(other.Watts);

    public override string ToString() =>
        Watts >= 1000
            ? string.Format(System.Globalization.CultureInfo.InvariantCulture, "{0:F2} kW", Kilowatts)
            : string.Format(System.Globalization.CultureInfo.InvariantCulture, "{0:F0} W", Watts);
}
