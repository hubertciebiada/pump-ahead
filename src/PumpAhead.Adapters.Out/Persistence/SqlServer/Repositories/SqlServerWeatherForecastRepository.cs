using Microsoft.EntityFrameworkCore;
using PumpAhead.Adapters.Out.Persistence.SqlServer.Entities;
using PumpAhead.UseCases.Ports.Out;

namespace PumpAhead.Adapters.Out.Persistence.SqlServer.Repositories;

public class SqlServerWeatherForecastRepository(PumpAheadDbContext dbContext) : IWeatherForecastRepository
{
    public async Task SaveForecastAsync(
        IReadOnlyList<WeatherForecastPoint> points,
        DateTimeOffset fetchedAt,
        CancellationToken cancellationToken = default)
    {
        var entities = points.Select(p => new WeatherForecastEntity
        {
            TemperatureCelsius = p.TemperatureCelsius,
            ForecastTimestamp = p.ForecastTimestamp,
            FetchedAt = fetchedAt
        });

        dbContext.WeatherForecasts.AddRange(entities);
        await dbContext.SaveChangesAsync(cancellationToken);
    }

    public async Task<IReadOnlyList<WeatherForecastPoint>> GetForecastFromAsync(
        DateTimeOffset from,
        int hours = 12,
        CancellationToken cancellationToken = default)
    {
        var to = from.AddHours(hours);

        // Get the latest fetch for forecast data covering the requested range
        var latestFetchedAt = await dbContext.WeatherForecasts
            .Where(e => e.ForecastTimestamp >= from && e.ForecastTimestamp <= to)
            .MaxAsync(e => (DateTimeOffset?)e.FetchedAt, cancellationToken);

        if (latestFetchedAt == null)
            return [];

        return await dbContext.WeatherForecasts
            .Where(e => e.FetchedAt == latestFetchedAt.Value
                        && e.ForecastTimestamp >= from
                        && e.ForecastTimestamp <= to)
            .OrderBy(e => e.ForecastTimestamp)
            .Select(e => new WeatherForecastPoint(e.TemperatureCelsius, e.ForecastTimestamp))
            .ToListAsync(cancellationToken);
    }
}
