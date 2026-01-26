namespace PumpAhead.Startup.Configuration;

public class DeviceSettings
{
    public HeishamonSettings Heishamon { get; set; } = new();
}

public class HeishamonSettings
{
    public string Address { get; set; } = "http://heishamon.local";
}
