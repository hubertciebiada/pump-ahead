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
            existing.Compressor_Frequency = heatPump.CompressorFrequency.Hertz;

            // Power data
            existing.Power_HeatProduction = heatPump.Power.HeatProduction.Watts;
            existing.Power_HeatConsumption = heatPump.Power.HeatConsumption.Watts;
            existing.Power_CoolProduction = heatPump.Power.CoolProduction.Watts;
            existing.Power_CoolConsumption = heatPump.Power.CoolConsumption.Watts;
            existing.Power_DhwProduction = heatPump.Power.DhwProduction.Watts;
            existing.Power_DhwConsumption = heatPump.Power.DhwConsumption.Watts;

            // Operations data
            existing.Operations_CompressorHours = heatPump.Operations.CompressorHours;
            existing.Operations_CompressorStarts = heatPump.Operations.CompressorStarts;

            // Defrost
            existing.Defrost_IsActive = heatPump.Defrost.IsActive;

            // Error code
            existing.ErrorCode = heatPump.ErrorCode.Code;
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

        var power = new PowerData(
            Power.FromWatts(entity.Power_HeatProduction),
            Power.FromWatts(entity.Power_HeatConsumption),
            Power.FromWatts(entity.Power_CoolProduction),
            Power.FromWatts(entity.Power_CoolConsumption),
            Power.FromWatts(entity.Power_DhwProduction),
            Power.FromWatts(entity.Power_DhwConsumption));

        var operations = new OperationsData(
            entity.Operations_CompressorHours,
            entity.Operations_CompressorStarts);

        var defrost = new DefrostData(entity.Defrost_IsActive);

        var errorCode = ErrorCode.From(entity.ErrorCode);

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
            Frequency.FromHertz(entity.Compressor_Frequency),
            power,
            operations,
            defrost,
            errorCode);
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
            Compressor_Frequency = heatPump.CompressorFrequency.Hertz,
            Power_HeatProduction = heatPump.Power.HeatProduction.Watts,
            Power_HeatConsumption = heatPump.Power.HeatConsumption.Watts,
            Power_CoolProduction = heatPump.Power.CoolProduction.Watts,
            Power_CoolConsumption = heatPump.Power.CoolConsumption.Watts,
            Power_DhwProduction = heatPump.Power.DhwProduction.Watts,
            Power_DhwConsumption = heatPump.Power.DhwConsumption.Watts,
            Operations_CompressorHours = heatPump.Operations.CompressorHours,
            Operations_CompressorStarts = heatPump.Operations.CompressorStarts,
            Defrost_IsActive = heatPump.Defrost.IsActive,
            ErrorCode = heatPump.ErrorCode.Code
        };
    }
}
