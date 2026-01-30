using PumpAhead.DeepModel.Entities;
using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.UseCases.Ports.Out;

/// <summary>
/// Repository for heat pump historical snapshots.
/// </summary>
public interface IHeatPumpSnapshotRepository
{
    /// <summary>
    /// Saves a new snapshot to the database.
    /// </summary>
    Task SaveSnapshotAsync(HeatPumpSnapshot snapshot, CancellationToken cancellationToken = default);

    /// <summary>
    /// Retrieves snapshots for a heat pump within a time range.
    /// Results are ordered by timestamp ascending.
    /// </summary>
    Task<IReadOnlyList<HeatPumpSnapshot>> GetHistoryAsync(
        HeatPumpId heatPumpId,
        DateTimeOffset from,
        DateTimeOffset to,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Retrieves the most recent snapshot for a heat pump.
    /// Returns null if no snapshots exist.
    /// </summary>
    Task<HeatPumpSnapshot?> GetLatestSnapshotAsync(
        HeatPumpId heatPumpId,
        CancellationToken cancellationToken = default);
}
