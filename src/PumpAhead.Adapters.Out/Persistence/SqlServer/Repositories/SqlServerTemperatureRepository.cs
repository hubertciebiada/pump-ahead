using Microsoft.EntityFrameworkCore;
using PumpAhead.Adapters.Out.Persistence.SqlServer.Entities;
using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.UseCases.Ports.Out;

namespace PumpAhead.Adapters.Out.Persistence.SqlServer.Repositories;

public class SqlServerTemperatureRepository(PumpAheadDbContext dbContext) : ITemperatureRepository
{
    public async Task SaveAsync(TemperatureReading reading, CancellationToken cancellationToken = default)
    {
        var entity = new TemperatureReadingEntity
        {
            SensorId = reading.SensorId.Value,
            Temperature = reading.Temperature.Celsius,
            Timestamp = reading.Timestamp
        };

        dbContext.TemperatureReadings.Add(entity);
        await dbContext.SaveChangesAsync(cancellationToken);
    }

    public async Task<TemperatureReading?> GetLatestAsync(SensorId sensorId, CancellationToken cancellationToken = default)
    {
        var entity = await dbContext.TemperatureReadings
            .Where(r => r.SensorId == sensorId.Value)
            .OrderByDescending(r => r.Timestamp)
            .FirstOrDefaultAsync(cancellationToken);

        if (entity is null)
            return null;

        return new TemperatureReading(
            SensorId.From(entity.SensorId),
            Temperature.FromCelsius(entity.Temperature),
            entity.Timestamp);
    }

    public async Task<IReadOnlyList<TemperatureReading>> GetHistoryAsync(
        SensorId sensorId,
        DateTimeOffset from,
        DateTimeOffset to,
        CancellationToken cancellationToken = default)
    {
        var entities = await dbContext.TemperatureReadings
            .Where(r => r.SensorId == sensorId.Value && r.Timestamp >= from && r.Timestamp <= to)
            .OrderBy(r => r.Timestamp)
            .ToListAsync(cancellationToken);

        return entities
            .Select(e => new TemperatureReading(
                SensorId.From(e.SensorId),
                Temperature.FromCelsius(e.Temperature),
                e.Timestamp))
            .ToList();
    }
}
