using Microsoft.EntityFrameworkCore;
using PumpAhead.Adapters.Out.Persistence.SqlServer.Entities;
using PumpAhead.DeepModel;
using PumpAhead.DeepModel.Aggregates;
using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.UseCases.Ports.Out;

namespace PumpAhead.Adapters.Out.Persistence.SqlServer.Repositories;

public class SqlServerHeatPumpRepository(PumpAheadDbContext context) : IHeatPumpRepository
{
    public async Task<HeatPump?> GetByIdAsync(HeatPumpId id, CancellationToken cancellationToken = default)
    {
        var entity = await context.HeatPumps
            .AsNoTracking()
            .FirstOrDefaultAsync(hp => hp.Id == id.Value, cancellationToken);

        return entity is null ? null : MapToDomain(entity);
    }

    public async Task<HeatPump?> GetDefaultAsync(CancellationToken cancellationToken = default)
    {
        var entity = await context.HeatPumps
            .AsNoTracking()
            .OrderByDescending(hp => hp.LastSyncTime)
            .FirstOrDefaultAsync(cancellationToken);

        return entity is null ? null : MapToDomain(entity);
    }

    public async Task<IReadOnlyList<HeatPump>> GetAllAsync(CancellationToken cancellationToken = default)
    {
        var entities = await context.HeatPumps
            .AsNoTracking()
            .ToListAsync(cancellationToken);

        return entities.Select(MapToDomain).ToList();
    }

    public async Task SaveAsync(HeatPump heatPump, CancellationToken cancellationToken = default)
    {
        var existing = await context.HeatPumps
            .FirstOrDefaultAsync(hp => hp.Id == heatPump.Id.Value, cancellationToken);

        if (existing is null)
        {
            var entity = MapToEntity(heatPump);
            context.HeatPumps.Add(entity);
        }
        else
        {
            existing.Model = heatPump.Model;
            existing.LastSyncTime = heatPump.LastSyncTime;
            existing.OperatingMode = (int)heatPump.OperatingMode;
            existing.CH_FlowTemperature = heatPump.CentralHeating.FlowTemperature.Celsius;
            existing.CH_ReturnTemperature = heatPump.CentralHeating.ReturnTemperature.Celsius;
            existing.CH_Offset = heatPump.CentralHeating.Offset.Celsius;
            existing.DHW_ActualTemperature = heatPump.DomesticHotWater.ActualTemperature.Celsius;
            existing.DHW_TargetTemperature = heatPump.DomesticHotWater.TargetTemperature.Celsius;
            existing.DHW_Delta = heatPump.DomesticHotWater.Delta.Celsius;
            existing.Compressor_Frequency = heatPump.Compressor.Frequency.Hertz;
        }

        await context.SaveChangesAsync(cancellationToken);
    }

    public async Task<bool> ExistsAsync(HeatPumpId id, CancellationToken cancellationToken = default)
    {
        return await context.HeatPumps
            .AnyAsync(hp => hp.Id == id.Value, cancellationToken);
    }

    private static HeatPump MapToDomain(HeatPumpEntity entity)
    {
        var centralHeating = CentralHeatingData.Create(
            FlowTemperature.FromCelsius(entity.CH_FlowTemperature),
            ReturnTemperature.FromCelsius(entity.CH_ReturnTemperature),
            TemperatureOffset.FromCelsius(entity.CH_Offset));

        var domesticHotWater = DomesticHotWaterData.Create(
            DhwTemperature.FromCelsius(entity.DHW_ActualTemperature),
            DhwTemperature.FromCelsius(entity.DHW_TargetTemperature),
            TemperatureOffset.FromCelsius(entity.DHW_Delta));

        var compressor = CompressorData.Create(
            Frequency.FromHertz(entity.Compressor_Frequency));

        return HeatPump.Reconstitute(
            HeatPumpId.From(entity.Id),
            entity.Model,
            entity.LastSyncTime,
            (OperatingMode)entity.OperatingMode,
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
            OperatingMode = (int)heatPump.OperatingMode,
            CH_FlowTemperature = heatPump.CentralHeating.FlowTemperature.Celsius,
            CH_ReturnTemperature = heatPump.CentralHeating.ReturnTemperature.Celsius,
            CH_Offset = heatPump.CentralHeating.Offset.Celsius,
            DHW_ActualTemperature = heatPump.DomesticHotWater.ActualTemperature.Celsius,
            DHW_TargetTemperature = heatPump.DomesticHotWater.TargetTemperature.Celsius,
            DHW_Delta = heatPump.DomesticHotWater.Delta.Celsius,
            Compressor_Frequency = heatPump.Compressor.Frequency.Hertz
        };
    }
}
