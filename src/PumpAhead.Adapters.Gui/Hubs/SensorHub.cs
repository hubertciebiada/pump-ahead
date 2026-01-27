using Microsoft.AspNetCore.SignalR;

namespace PumpAhead.Adapters.Gui.Hubs;

public sealed class SensorHub : Hub<ISensorHubClient>
{
}
