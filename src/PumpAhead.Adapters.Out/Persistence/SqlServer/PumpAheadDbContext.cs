using Microsoft.EntityFrameworkCore;
using PumpAhead.Adapters.Out.Persistence.SqlServer.Entities;

namespace PumpAhead.Adapters.Out.Persistence.SqlServer;

public class PumpAheadDbContext(DbContextOptions<PumpAheadDbContext> options) : DbContext(options)
{
    public DbSet<SensorEntity> Sensors => Set<SensorEntity>();
    public DbSet<TemperatureReadingEntity> TemperatureReadings => Set<TemperatureReadingEntity>();
    public DbSet<HeatPumpEntity> HeatPumps => Set<HeatPumpEntity>();
    public DbSet<HeatPumpSnapshotEntity> HeatPumpSnapshots => Set<HeatPumpSnapshotEntity>();
    public DbSet<WeatherForecastEntity> WeatherForecasts => Set<WeatherForecastEntity>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.ApplyConfigurationsFromAssembly(typeof(PumpAheadDbContext).Assembly);
    }
}
