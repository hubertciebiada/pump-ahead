using Microsoft.AspNetCore.SignalR;
using PumpAhead.Adapters.Gui.Hubs;
using PumpAhead.UseCases.Ports.Out;

namespace PumpAhead.Adapters.Gui.Services;

public sealed class SignalRHeatPumpNotificationService(
    IHubContext<SensorHub, ISensorHubClient> hubContext) : IHeatPumpNotificationService
{
    public async Task NotifyHeatPumpUpdatedAsync()
    {
        await hubContext.Clients.All.ReceiveHeatPumpUpdate();
    }

    public async Task NotifyConnectionFailureAsync(int consecutiveFailures)
    {
        await hubContext.Clients.All.ReceiveHeatPumpConnectionFailure(consecutiveFailures);
    }
}
