using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.UseCases.Ports.Out;

public record SensorInfo(
    SensorId Id,
    string Name,
    string? Label,
    string Address,
    string Type,
    bool IsActive,
    DateTimeOffset? LastSeenAt)
{
    public string DisplayName => !string.IsNullOrWhiteSpace(Label) ? Label : Id.Value;
}

public interface ISensorRepository
{
    Task<SensorInfo?> GetByIdAsync(SensorId id, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<SensorInfo>> GetAllActiveAsync(CancellationToken cancellationToken = default);
    Task SaveAsync(SensorInfo sensor, CancellationToken cancellationToken = default);
    Task UpdateLastSeenAsync(SensorId id, DateTimeOffset timestamp, CancellationToken cancellationToken = default);
}
