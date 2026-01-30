namespace PumpAhead.DeepModel.ValueObjects;

/// <summary>
/// Strongly-typed identifier for heat pump snapshots.
/// </summary>
public readonly record struct HeatPumpSnapshotId(long Value)
{
    public static HeatPumpSnapshotId From(long id) => new(id);

    public override string ToString() => Value.ToString();
}
