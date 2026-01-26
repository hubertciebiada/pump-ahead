using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.UseCases.Ports.Out;

public interface ISensorNotificationService
{
    Task NotifyReadingRecordedAsync(SensorId sensorId, Temperature temperature, DateTimeOffset timestamp, CancellationToken cancellationToken = default);
}
