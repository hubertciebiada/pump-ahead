namespace PumpAhead.Adapters.Gui.Hubs;

public interface ISensorHubClient
{
    Task ReceiveSensorUpdate(string sensorId, decimal temperature, long timestamp);
}
