using Microsoft.EntityFrameworkCore;
using PumpAhead.Adapters.Out.Persistence.SqlServer.Entities;
using PumpAhead.DeepModel;
using PumpAhead.DeepModel.Aggregates;
using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.UseCases.Ports.Out;

namespace PumpAhead.Adapters.Out.Persistence.SqlServer.Repositories;

public class SqlServerHeatPumpRepository(PumpAheadDbContext dbContext) : IHeatPumpRepository
{
    public async Task<HeatPump?> GetByIdAsync(HeatPumpId id, CancellationToken cancellationToken = default)
    {
        var entity = await dbContext.HeatPumps
            .AsNoTracking()
            .FirstOrDefaultAsync(hp => hp.Id == id.Value, cancellationToken);

        return entity is null ? null : MapToDomain(entity);
    }

    public async Task<HeatPump?> GetDefaultAsync(CancellationToken cancellationToken = default)
    {
        var entity = await dbContext.HeatPumps
            .AsNoTracking()
            .OrderByDescending(hp => hp.LastSyncTime)
            .FirstOrDefaultAsync(cancellationToken);

        return entity is null ? null : MapToDomain(entity);
    }

    public async Task<IReadOnlyList<HeatPump>> GetAllAsync(CancellationToken cancellationToken = default)
    {
        var entities = await dbContext.HeatPumps
            .AsNoTracking()
            .ToListAsync(cancellationToken);

        return entities.Select(MapToDomain).ToList();
    }

    public async Task SaveAsync(HeatPump heatPump, CancellationToken cancellationToken = default)
    {
        var existing = await dbContext.HeatPumps
            .FirstOrDefaultAsync(hp => hp.Id == heatPump.Id.Value, cancellationToken);

        if (existing is null)
        {
            var entity = MapToEntity(heatPump);
            dbContext.HeatPumps.Add(entity);
        }
        else
        {
            existing.Model = heatPump.Model;
            existing.LastSyncTime = heatPump.LastSyncTime;
            existing.IsOn = heatPump.IsOn;
            existing.OperatingMode = (int)heatPump.OperatingMode;
            existing.PumpFlow = heatPump.PumpFlow.LitersPerMinute;
            existing.OutsideTemperature = heatPump.OutsideTemperature.Celsius;
            existing.CH_InletTemperature = heatPump.CentralHeating.InletTemperature.Celsius;
            existing.CH_OutletTemperature = heatPump.CentralHeating.OutletTemperature.Celsius;
            existing.CH_TargetTemperature = heatPump.CentralHeating.TargetTemperature.Celsius;
            existing.DHW_ActualTemperature = heatPump.DomesticHotWater.ActualTemperature.Celsius;
            existing.DHW_TargetTemperature = heatPump.DomesticHotWater.TargetTemperature.Celsius;
            existing.Compressor_Frequency = heatPump.Compressor.Frequency.Hertz;
        }

        await dbContext.SaveChangesAsync(cancellationToken);
    }

    public async Task<bool> ExistsAsync(HeatPumpId id, CancellationToken cancellationToken = default)
    {
        return await dbContext.HeatPumps
            .AnyAsync(hp => hp.Id == id.Value, cancellationToken);
    }

    private static HeatPump MapToDomain(HeatPumpEntity entity)
    {
        var centralHeating = new CentralHeatingData(
            WaterTemperature.FromCelsius(entity.CH_InletTemperature),
            WaterTemperature.FromCelsius(entity.CH_OutletTemperature),
            WaterTemperature.FromCelsius(entity.CH_TargetTemperature));

        var domesticHotWater = new DomesticHotWaterData(
            DhwTemperature.FromCelsius(entity.DHW_ActualTemperature),
            DhwTemperature.FromCelsius(entity.DHW_TargetTemperature));

        var compressor = CompressorData.Create(
            Frequency.FromHertz(entity.Compressor_Frequency));

        return HeatPump.Reconstitute(
            HeatPumpId.From(entity.Id),
            entity.Model,
            entity.LastSyncTime,
            entity.IsOn,
            (OperatingMode)entity.OperatingMode,
            PumpFlow.FromLitersPerMinute(entity.PumpFlow),
            OutsideTemperature.FromCelsius(entity.OutsideTemperature),
            centralHeating,
            domesticHotWater,
            compressor);
    }

    private static HeatPumpEntity MapToEntity(HeatPump heatPump)
    {
        return new HeatPumpEntity
        {
            Id = heatPump.Id.Value,
            Model = heatPump.Model,
            LastSyncTime = heatPump.LastSyncTime,
            IsOn = heatPump.IsOn,
            OperatingMode = (int)heatPump.OperatingMode,
            PumpFlow = heatPump.PumpFlow.LitersPerMinute,
            OutsideTemperature = heatPump.OutsideTemperature.Celsius,
            CH_InletTemperature = heatPump.CentralHeating.InletTemperature.Celsius,
            CH_OutletTemperature = heatPump.CentralHeating.OutletTemperature.Celsius,
            CH_TargetTemperature = heatPump.CentralHeating.TargetTemperature.Celsius,
            DHW_ActualTemperature = heatPump.DomesticHotWater.ActualTemperature.Celsius,
            DHW_TargetTemperature = heatPump.DomesticHotWater.TargetTemperature.Celsius,
            Compressor_Frequency = heatPump.Compressor.Frequency.Hertz
        };
    }
}
