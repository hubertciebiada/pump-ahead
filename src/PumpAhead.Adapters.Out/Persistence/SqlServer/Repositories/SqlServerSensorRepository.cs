using Microsoft.EntityFrameworkCore;
using PumpAhead.Adapters.Out.Persistence.SqlServer.Entities;
using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.UseCases.Ports.Out;

namespace PumpAhead.Adapters.Out.Persistence.SqlServer.Repositories;

public class SqlServerSensorRepository(PumpAheadDbContext dbContext) : ISensorRepository
{
    public async Task<SensorInfo?> GetByIdAsync(SensorId id, CancellationToken cancellationToken = default)
    {
        var entity = await dbContext.Sensors
            .FirstOrDefaultAsync(s => s.Id == id.Value, cancellationToken);

        if (entity is null)
            return null;

        return ToSensorInfo(entity);
    }

    public async Task<IReadOnlyList<SensorInfo>> GetAllActiveAsync(CancellationToken cancellationToken = default)
    {
        var entities = await dbContext.Sensors
            .Where(s => s.IsActive)
            .ToListAsync(cancellationToken);

        return entities.Select(ToSensorInfo).ToList();
    }

    public async Task SaveAsync(SensorInfo sensor, CancellationToken cancellationToken = default)
    {
        var existing = await dbContext.Sensors
            .FirstOrDefaultAsync(s => s.Id == sensor.Id.Value, cancellationToken);

        if (existing is null)
        {
            var entity = new SensorEntity
            {
                Id = sensor.Id.Value,
                Name = sensor.Name,
                Address = sensor.Address,
                Type = sensor.Type,
                IsActive = sensor.IsActive,
                LastSeenAt = sensor.LastSeenAt
            };
            dbContext.Sensors.Add(entity);
        }
        else
        {
            existing.Name = sensor.Name;
            existing.Address = sensor.Address;
            existing.Type = sensor.Type;
            existing.IsActive = sensor.IsActive;
            existing.LastSeenAt = sensor.LastSeenAt;
        }

        await dbContext.SaveChangesAsync(cancellationToken);
    }

    public async Task UpdateLastSeenAsync(SensorId id, DateTimeOffset timestamp, CancellationToken cancellationToken = default)
    {
        await dbContext.Sensors
            .Where(s => s.Id == id.Value)
            .ExecuteUpdateAsync(s => s.SetProperty(x => x.LastSeenAt, timestamp), cancellationToken);
    }

    private static SensorInfo ToSensorInfo(SensorEntity entity) =>
        new(
            SensorId.From(entity.Id),
            entity.Name,
            entity.Address,
            entity.Type,
            entity.IsActive,
            entity.LastSeenAt);
}
