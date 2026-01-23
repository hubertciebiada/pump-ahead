using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.UseCases.Ports;
using PumpAhead.UseCases.Ports.Out;

namespace PumpAhead.UseCases.Queries.GetTemperature;

public static class GetTemperature
{
    public sealed record Query(SensorId SensorId);

    public sealed record Data(Temperature Temperature, DateTimeOffset Timestamp);

    public sealed class Handler(ITemperatureRepository repository) : IQueryHandler<Query, Data?>
    {
        public async Task<Data?> HandleAsync(Query query, CancellationToken cancellationToken = default)
        {
            var reading = await repository.GetLatestAsync(query.SensorId, cancellationToken);

            if (reading is null)
                return null;

            return new Data(reading.Value.Temperature, reading.Value.Timestamp);
        }
    }
}
