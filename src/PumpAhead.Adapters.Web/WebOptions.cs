namespace PumpAhead.Adapters.Web;

public class WebOptions
{
    public string DefaultSensorId { get; set; } = string.Empty;
    public int ForecastOffsetHours { get; set; } = 6;
    public double TargetIndoorTemperature { get; set; } = 22.0;
}
