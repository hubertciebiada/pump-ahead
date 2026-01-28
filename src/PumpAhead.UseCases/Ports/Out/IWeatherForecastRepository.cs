namespace PumpAhead.UseCases.Ports.Out;

public interface IWeatherForecastRepository
{
    Task SaveForecastAsync(
        IReadOnlyList<WeatherForecastPoint> points,
        DateTimeOffset fetchedAt,
        CancellationToken cancellationToken = default);

    Task<IReadOnlyList<WeatherForecastPoint>> GetForecastFromAsync(
        DateTimeOffset from,
        int hours = 12,
        CancellationToken cancellationToken = default);
}
