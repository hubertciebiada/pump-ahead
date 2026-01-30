namespace PumpAhead.DeepModel.ValueObjects;

/// <summary>
/// Power production and consumption data for heat pump.
/// HeishaMon TOP15-TOP18: Heat/Cool/DHW Power.
/// </summary>
public readonly record struct PowerData(
    Power HeatProduction,
    Power HeatConsumption,
    Power CoolProduction,
    Power CoolConsumption,
    Power DhwProduction,
    Power DhwConsumption)
{
    /// <summary>
    /// Current COP (Coefficient of Performance) for heating.
    /// Returns 0 if consumption is zero.
    /// </summary>
    public decimal HeatingCop =>
        HeatConsumption.Watts > 0
            ? Math.Round(HeatProduction.Watts / HeatConsumption.Watts, 2)
            : 0;

    /// <summary>
    /// Current COP for DHW heating.
    /// Returns 0 if consumption is zero.
    /// </summary>
    public decimal DhwCop =>
        DhwConsumption.Watts > 0
            ? Math.Round(DhwProduction.Watts / DhwConsumption.Watts, 2)
            : 0;

    /// <summary>
    /// Total power consumption across all modes.
    /// </summary>
    public Power TotalConsumption =>
        Power.FromWatts(HeatConsumption.Watts + CoolConsumption.Watts + DhwConsumption.Watts);

    public static PowerData Zero => new(
        Power.Zero, Power.Zero,
        Power.Zero, Power.Zero,
        Power.Zero, Power.Zero);
}
