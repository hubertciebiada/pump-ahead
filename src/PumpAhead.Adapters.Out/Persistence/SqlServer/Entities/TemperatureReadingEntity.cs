namespace PumpAhead.Adapters.Out.Persistence.SqlServer.Entities;

public class TemperatureReadingEntity
{
    public long Id { get; set; }
    public Guid SensorId { get; set; }
    public decimal Temperature { get; set; }
    public DateTimeOffset Timestamp { get; set; }

    public SensorEntity? Sensor { get; set; }
}
