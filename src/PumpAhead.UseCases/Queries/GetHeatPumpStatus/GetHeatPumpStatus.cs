using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.UseCases.Ports;
using PumpAhead.UseCases.Ports.Out;

namespace PumpAhead.UseCases.Queries.GetHeatPumpStatus;

public static class GetHeatPumpStatus
{
    public sealed record Query(HeatPumpId HeatPumpId);

    public sealed record Data(
        HeatPumpId Id,
        string Model,
        DateTimeOffset LastSyncTime,
        bool IsOn,
        string OperatingMode,
        decimal PumpFlowLitersPerMinute,
        decimal OutsideTemperatureCelsius,
        decimal CH_InletTemperatureCelsius,
        decimal CH_OutletTemperatureCelsius,
        decimal CH_TargetTemperatureCelsius,
        decimal DHW_ActualTemperatureCelsius,
        decimal DHW_TargetTemperatureCelsius,
        decimal CompressorFrequencyHertz,
        decimal HeatPowerProductionWatts,
        decimal HeatPowerConsumptionWatts,
        decimal HeatingCop,
        decimal CompressorOperatingHours,
        int CompressorStartCount,
        bool IsDefrosting,
        string ErrorCode,
        bool HasError);

    public sealed class Handler(IHeatPumpRepository repository) : IQueryHandler<Query, Data?>
    {
        public async Task<Data?> HandleAsync(Query query, CancellationToken cancellationToken = default)
        {
            var heatPump = await repository.GetByIdAsync(query.HeatPumpId, cancellationToken);
            if (heatPump is null)
                return null;

            return new Data(
                heatPump.Id,
                heatPump.Model,
                heatPump.LastSyncTime,
                heatPump.IsOn,
                heatPump.OperatingMode.ToString(),
                heatPump.PumpFlow.LitersPerMinute,
                heatPump.OutsideTemperature.Celsius,
                heatPump.CentralHeating.InletTemperature.Celsius,
                heatPump.CentralHeating.OutletTemperature.Celsius,
                heatPump.CentralHeating.TargetTemperature.Celsius,
                heatPump.DomesticHotWater.ActualTemperature.Celsius,
                heatPump.DomesticHotWater.TargetTemperature.Celsius,
                heatPump.CompressorFrequency.Hertz,
                heatPump.Power.HeatProduction.Watts,
                heatPump.Power.HeatConsumption.Watts,
                heatPump.Power.HeatingCop,
                heatPump.Operations.CompressorHours,
                heatPump.Operations.CompressorStarts,
                heatPump.Defrost.IsActive,
                heatPump.ErrorCode.Code,
                heatPump.ErrorCode.HasError);
        }
    }
}
