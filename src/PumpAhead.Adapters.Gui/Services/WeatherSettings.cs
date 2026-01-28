namespace PumpAhead.Adapters.Gui.Services;

public class WeatherSettings
{
    public double Latitude { get; set; } = 50.71454842957479;
    public double Longitude { get; set; } = 17.345668709344523;
    public int RefreshIntervalMinutes { get; set; } = 15;
    public int ForecastHours { get; set; } = 24;
}
