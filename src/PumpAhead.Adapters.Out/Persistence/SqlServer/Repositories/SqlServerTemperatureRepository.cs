using Microsoft.EntityFrameworkCore;
using PumpAhead.Adapters.Out.Persistence.SqlServer.Entities;
using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.UseCases.Ports.Out;

namespace PumpAhead.Adapters.Out.Persistence.SqlServer.Repositories;

public class SqlServerTemperatureRepository(PumpAheadDbContext dbContext) : ITemperatureRepository
{
    public async Task SaveAsync(SensorReading reading, CancellationToken cancellationToken = default)
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

    public async Task<SensorReading?> GetLatestAsync(SensorId sensorId, CancellationToken cancellationToken = default)
    {
        var entity = await dbContext.TemperatureReadings
            .Where(r => r.SensorId == sensorId.Value)
            .OrderByDescending(r => r.Timestamp)
            .FirstOrDefaultAsync(cancellationToken);

        if (entity is null)
            return null;

        return new SensorReading(
            SensorId.From(entity.SensorId),
            Temperature.FromCelsius(entity.Temperature),
            entity.Timestamp);
    }

    public async Task<IReadOnlyList<SensorReading>> GetHistoryAsync(
        SensorId sensorId,
        DateTimeOffset from,
        DateTimeOffset to,
        CancellationToken cancellationToken = default)
    {
        return await dbContext.TemperatureReadings
            .Where(r => r.SensorId == sensorId.Value && r.Timestamp >= from && r.Timestamp <= to)
            .OrderBy(r => r.Timestamp)
            .Select(e => new SensorReading(
                SensorId.From(e.SensorId),
                Temperature.FromCelsius(e.Temperature),
                e.Timestamp))
            .ToListAsync(cancellationToken);
    }
}
