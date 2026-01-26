using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.UseCases.Ports.Out;

public interface ITemperatureRepository
{
    Task SaveAsync(SensorReading reading, CancellationToken cancellationToken = default);
    Task<SensorReading?> GetLatestAsync(SensorId sensorId, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<SensorReading>> GetHistoryAsync(
        SensorId sensorId,
        DateTimeOffset from,
        DateTimeOffset to,
        CancellationToken cancellationToken = default);
}
