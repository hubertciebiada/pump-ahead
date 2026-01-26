namespace PumpAhead.Adapters.Out.Persistence.SqlServer.Entities;

public class SensorEntity
{
    public string Id { get; set; } = string.Empty;
    public string Name { get; set; } = string.Empty;
    public string Address { get; set; } = string.Empty;
    public string Type { get; set; } = string.Empty;
    public bool IsActive { get; set; }
    public DateTimeOffset? LastSeenAt { get; set; }

    public ICollection<TemperatureReadingEntity> Readings { get; set; } = [];
}
