using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.UseCases.Ports.Out;

public interface ITemperatureRepository
{
    Task SaveAsync(TemperatureReading reading, CancellationToken cancellationToken = default);
    Task<TemperatureReading?> GetLatestAsync(SensorId sensorId, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<TemperatureReading>> GetHistoryAsync(
        SensorId sensorId,
        DateTimeOffset from,
        DateTimeOffset to,
        CancellationToken cancellationToken = default);
}
