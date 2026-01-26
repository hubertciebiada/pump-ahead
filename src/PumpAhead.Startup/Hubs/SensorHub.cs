using Microsoft.AspNetCore.SignalR;

namespace PumpAhead.Startup.Hubs;

public sealed class SensorHub : Hub<ISensorHubClient>
{
}
