namespace PumpAhead.Startup.Configuration;

public class PollingSettings
{
    public int ShellyIntervalMinutes { get; set; } = 5;
    public int ControlIntervalMinutes { get; set; } = 30;
}
