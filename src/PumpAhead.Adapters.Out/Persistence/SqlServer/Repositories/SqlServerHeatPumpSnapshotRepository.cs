using Microsoft.EntityFrameworkCore;
using PumpAhead.Adapters.Out.Persistence.SqlServer.Entities;
using PumpAhead.DeepModel;
using PumpAhead.DeepModel.Entities;
using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.UseCases.Ports.Out;

namespace PumpAhead.Adapters.Out.Persistence.SqlServer.Repositories;

public class SqlServerHeatPumpSnapshotRepository(PumpAheadDbContext dbContext) : IHeatPumpSnapshotRepository
{
    public async Task SaveSnapshotAsync(HeatPumpSnapshot snapshot, CancellationToken cancellationToken = default)
    {
        var entity = MapToEntity(snapshot);
        dbContext.HeatPumpSnapshots.Add(entity);
        await dbContext.SaveChangesAsync(cancellationToken);
    }

    public async Task<IReadOnlyList<HeatPumpSnapshot>> GetHistoryAsync(
        HeatPumpId heatPumpId,
        DateTimeOffset from,
        DateTimeOffset to,
        CancellationToken cancellationToken = default)
    {
        var entities = await dbContext.HeatPumpSnapshots
            .AsNoTracking()
            .Where(s => s.HeatPumpId == heatPumpId.Value
                && s.Timestamp >= from
                && s.Timestamp <= to)
            .OrderBy(s => s.Timestamp)
            .ToListAsync(cancellationToken);

        return entities.Select(MapToDomain).ToList();
    }

    public async Task<HeatPumpSnapshot?> GetLatestSnapshotAsync(
        HeatPumpId heatPumpId,
        CancellationToken cancellationToken = default)
    {
        var entity = await dbContext.HeatPumpSnapshots
            .AsNoTracking()
            .Where(s => s.HeatPumpId == heatPumpId.Value)
            .OrderByDescending(s => s.Timestamp)
            .FirstOrDefaultAsync(cancellationToken);

        return entity is null ? null : MapToDomain(entity);
    }

    private static HeatPumpSnapshot MapToDomain(HeatPumpSnapshotEntity entity)
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

        return HeatPumpSnapshot.Reconstitute(
            HeatPumpSnapshotId.From(entity.Id),
            HeatPumpId.From(entity.HeatPumpId),
            entity.Timestamp,
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

    private static HeatPumpSnapshotEntity MapToEntity(HeatPumpSnapshot snapshot)
    {
        return new HeatPumpSnapshotEntity
        {
            HeatPumpId = snapshot.HeatPumpId.Value,
            Timestamp = snapshot.Timestamp,
            IsOn = snapshot.IsOn,
            OperatingMode = (int)snapshot.OperatingMode,
            PumpFlow = snapshot.PumpFlow.LitersPerMinute,
            OutsideTemperature = snapshot.OutsideTemperature.Celsius,
            CH_InletTemperature = snapshot.CentralHeating.InletTemperature.Celsius,
            CH_OutletTemperature = snapshot.CentralHeating.OutletTemperature.Celsius,
            CH_TargetTemperature = snapshot.CentralHeating.TargetTemperature.Celsius,
            DHW_ActualTemperature = snapshot.DomesticHotWater.ActualTemperature.Celsius,
            DHW_TargetTemperature = snapshot.DomesticHotWater.TargetTemperature.Celsius,
            Compressor_Frequency = snapshot.CompressorFrequency.Hertz,
            Power_HeatProduction = snapshot.Power.HeatProduction.Watts,
            Power_HeatConsumption = snapshot.Power.HeatConsumption.Watts,
            Power_CoolProduction = snapshot.Power.CoolProduction.Watts,
            Power_CoolConsumption = snapshot.Power.CoolConsumption.Watts,
            Power_DhwProduction = snapshot.Power.DhwProduction.Watts,
            Power_DhwConsumption = snapshot.Power.DhwConsumption.Watts,
            Operations_CompressorHours = snapshot.Operations.CompressorHours,
            Operations_CompressorStarts = snapshot.Operations.CompressorStarts,
            Defrost_IsActive = snapshot.Defrost.IsActive,
            ErrorCode = snapshot.ErrorCode.Code
        };
    }
}
