using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.UseCases.Ports;
using PumpAhead.UseCases.Ports.Out;

namespace PumpAhead.UseCases.Queries.GetHeatPumpHistory;

public static class GetHeatPumpHistory
{
    public sealed record Query(
        HeatPumpId HeatPumpId,
        DateTimeOffset From,
        DateTimeOffset To);

    public sealed record DataPoint(
        DateTimeOffset Timestamp,
        bool IsOn,
        decimal OutsideTemperatureCelsius,
        decimal CH_OutletTemperatureCelsius,
        decimal DHW_ActualTemperatureCelsius,
        decimal CompressorFrequencyHertz,
        decimal HeatPowerConsumptionWatts,
        decimal HeatingCop,
        bool IsDefrosting);

    public sealed record Data(IReadOnlyList<DataPoint> History);

    public sealed class Handler(IHeatPumpSnapshotRepository repository) : IQueryHandler<Query, Data>
    {
        public async Task<Data> HandleAsync(Query query, CancellationToken cancellationToken = default)
        {
            var snapshots = await repository.GetHistoryAsync(
                query.HeatPumpId,
                query.From,
                query.To,
                cancellationToken);

            var dataPoints = snapshots
                .Select(s => new DataPoint(
                    s.Timestamp,
                    s.IsOn,
                    s.OutsideTemperature.Celsius,
                    s.CentralHeating.OutletTemperature.Celsius,
                    s.DomesticHotWater.ActualTemperature.Celsius,
                    s.CompressorFrequency.Hertz,
                    s.Power.HeatConsumption.Watts,
                    s.Power.HeatingCop,
                    s.Defrost.IsActive))
                .ToList();

            return new Data(dataPoints);
        }
    }
}
