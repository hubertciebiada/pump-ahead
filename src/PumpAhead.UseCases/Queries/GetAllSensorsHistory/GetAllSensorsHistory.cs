using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.UseCases.Ports;
using PumpAhead.UseCases.Ports.Out;

namespace PumpAhead.UseCases.Queries.GetAllSensorsHistory;

public static class GetAllSensorsHistory
{
    public sealed record Query(DateTimeOffset From, DateTimeOffset To);

    public sealed record DataPoint(Temperature Temperature, DateTimeOffset Timestamp);

    public sealed record SensorData(SensorId SensorId, string DisplayName, IReadOnlyList<DataPoint> Readings);

    public sealed record Data(IReadOnlyList<SensorData> Sensors);

    public sealed class Handler(
        ISensorRepository sensorRepository,
        ITemperatureRepository temperatureRepository) : IQueryHandler<Query, Data>
    {
        public async Task<Data> HandleAsync(Query query, CancellationToken cancellationToken = default)
        {
            var sensors = await sensorRepository.GetAllActiveAsync(cancellationToken);

            var sensorDataList = new List<SensorData>();

            foreach (var sensor in sensors)
            {
                var readings = await temperatureRepository.GetHistoryAsync(
                    sensor.Id,
                    query.From,
                    query.To,
                    cancellationToken);

                var dataPoints = readings
                    .Select(r => new DataPoint(r.Temperature, r.Timestamp))
                    .ToList();

                sensorDataList.Add(new SensorData(sensor.Id, sensor.DisplayName, dataPoints));
            }

            return new Data(sensorDataList);
        }
    }
}
