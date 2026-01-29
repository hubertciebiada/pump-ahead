namespace PumpAhead.Adapters.Out.Persistence.SqlServer.Entities;

public class TemperatureReadingEntity
{
    public long Id { get; set; }
    public string SensorId { get; set; } = string.Empty;
    public decimal Temperature { get; set; }
    public DateTimeOffset Timestamp { get; set; }
}
