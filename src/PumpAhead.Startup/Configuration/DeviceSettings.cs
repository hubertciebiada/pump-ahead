namespace PumpAhead.Startup.Configuration;

public class DeviceSettings
{
    public ShellySettings Shelly { get; set; } = new();
    public HeishamonSettings Heishamon { get; set; } = new();
}

public class ShellySettings
{
    public string Address { get; set; } = "http://shelly-ht.local";
    public Guid SensorId { get; set; } = Guid.Empty;
}

public class HeishamonSettings
{
    public string Address { get; set; } = "http://heishamon.local";
}
