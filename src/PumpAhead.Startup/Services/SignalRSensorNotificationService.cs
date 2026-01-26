using Microsoft.AspNetCore.SignalR;
using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.Startup.Hubs;
using PumpAhead.UseCases.Ports.Out;

namespace PumpAhead.Startup.Services;

public sealed class SignalRSensorNotificationService(
    IHubContext<SensorHub, ISensorHubClient> hubContext) : ISensorNotificationService
{
    public async Task NotifyReadingRecordedAsync(
        SensorId sensorId,
        Temperature temperature,
        DateTimeOffset timestamp,
        CancellationToken cancellationToken = default)
    {
        await hubContext.Clients.All.ReceiveSensorUpdate(
            sensorId.Value,
            temperature.Celsius,
            timestamp.ToUnixTimeSeconds());
    }
}
