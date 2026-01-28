namespace PumpAhead.UseCases.Ports.Out;

public record WeatherForecastPoint(decimal TemperatureCelsius, DateTimeOffset ForecastTimestamp);

public record WeatherForecast(
    IReadOnlyList<WeatherForecastPoint> HourlyPoints,
    DateTimeOffset FetchedAt);

public interface IWeatherForecastProvider
{
    Task<WeatherForecast?> GetForecastAsync(
        double latitude,
        double longitude,
        int forecastHours = 12,
        CancellationToken cancellationToken = default);
}
