namespace PumpAhead.Adapters.Out.Persistence.SqlServer.Entities;

public class WeatherForecastEntity
{
    public long Id { get; set; }
    public decimal TemperatureCelsius { get; set; }
    public DateTimeOffset ForecastTimestamp { get; set; }
    public DateTimeOffset FetchedAt { get; set; }
}
