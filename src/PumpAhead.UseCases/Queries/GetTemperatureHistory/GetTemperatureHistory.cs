using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.UseCases.Ports;
using PumpAhead.UseCases.Ports.Out;

namespace PumpAhead.UseCases.Queries.GetTemperatureHistory;

public static class GetTemperatureHistory
{
    public sealed record Query(
        SensorId SensorId,
        DateTimeOffset From,
        DateTimeOffset To);

    public sealed record DataPoint(Temperature Temperature, DateTimeOffset Timestamp);

    public sealed record Data(IReadOnlyList<DataPoint> Readings);

    public sealed class Handler(ITemperatureRepository repository) : IQueryHandler<Query, Data>
    {
        public async Task<Data> HandleAsync(Query query, CancellationToken cancellationToken = default)
        {
            var readings = await repository.GetHistoryAsync(
                query.SensorId,
                query.From,
                query.To,
                cancellationToken);

            var dataPoints = readings
                .Select(r => new DataPoint(r.Temperature, r.Timestamp))
                .ToList();

            return new Data(dataPoints);
        }
    }
}
