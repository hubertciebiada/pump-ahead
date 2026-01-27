using PumpAhead.DeepModel.Aggregates;
using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.UseCases.Ports.Out;

public interface IHeatPumpRepository
{
    Task<HeatPump?> GetByIdAsync(HeatPumpId id, CancellationToken cancellationToken = default);
    Task<HeatPump?> GetDefaultAsync(CancellationToken cancellationToken = default);
    Task<IReadOnlyList<HeatPump>> GetAllAsync(CancellationToken cancellationToken = default);
    Task SaveAsync(HeatPump heatPump, CancellationToken cancellationToken = default);
    Task<bool> ExistsAsync(HeatPumpId id, CancellationToken cancellationToken = default);
}
