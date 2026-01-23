using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.UseCases.Ports.Out;

public record SensorInfo(
    SensorId Id,
    string Name,
    string Address,
    string Type,
    bool IsActive);

public interface ISensorRepository
{
    Task<SensorInfo?> GetByIdAsync(SensorId id, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<SensorInfo>> GetAllActiveAsync(CancellationToken cancellationToken = default);
    Task SaveAsync(SensorInfo sensor, CancellationToken cancellationToken = default);
}
