using PumpAhead.UseCases.Ports;
using PumpAhead.UseCases.Ports.Out;

namespace PumpAhead.UseCases.Queries.GetWeatherForecast;

public static class GetWeatherForecast
{
    public sealed record Query(DateTimeOffset From, int Hours = 12);

    public sealed record ForecastPoint(decimal TemperatureCelsius, DateTimeOffset Timestamp);

    public sealed record Data(IReadOnlyList<ForecastPoint> Points);

    public sealed class Handler(
        IWeatherForecastRepository forecastRepository) : IQueryHandler<Query, Data>
    {
        public async Task<Data> HandleAsync(Query query, CancellationToken cancellationToken = default)
        {
            var points = await forecastRepository.GetForecastFromAsync(
                query.From, query.Hours, cancellationToken);

            var forecastPoints = points
                .Select(p => new ForecastPoint(p.TemperatureCelsius, p.ForecastTimestamp))
                .ToList();

            return new Data(forecastPoints);
        }
    }
}
