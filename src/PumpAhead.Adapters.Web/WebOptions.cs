namespace PumpAhead.Adapters.Web;

public class WebOptions
{
    public Guid DefaultSensorId { get; set; } = Guid.Empty;
    public int ForecastOffsetHours { get; set; } = 6;
    public double TargetIndoorTemperature { get; set; } = 22.0;
}
