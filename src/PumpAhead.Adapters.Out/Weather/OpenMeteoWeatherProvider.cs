using System.Globalization;
using System.Net.Http.Json;
using System.Text.Json.Serialization;
using Microsoft.Extensions.Logging;
using PumpAhead.UseCases.Ports.Out;

namespace PumpAhead.Adapters.Out.Weather;

public class OpenMeteoWeatherProvider(
    HttpClient httpClient,
    ILogger<OpenMeteoWeatherProvider> logger) : IWeatherForecastProvider
{
    public async Task<WeatherForecast?> GetForecastAsync(
        double latitude,
        double longitude,
        int forecastHours = 12,
        CancellationToken cancellationToken = default)
    {
        var lat = latitude.ToString(CultureInfo.InvariantCulture);
        var lon = longitude.ToString(CultureInfo.InvariantCulture);
        var url = $"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m&forecast_hours={forecastHours}&timezone=auto";

        try
        {
            var response = await httpClient.GetFromJsonAsync<OpenMeteoResponse>(url, cancellationToken);
            if (response?.Hourly == null)
                return null;

            var fetchedAt = DateTimeOffset.UtcNow;
            var points = new List<WeatherForecastPoint>();

            for (var i = 0; i < response.Hourly.Time.Count; i++)
            {
                if (i < response.Hourly.Temperature2m.Count &&
                    DateTimeOffset.TryParse(response.Hourly.Time[i], out var timestamp))
                {
                    points.Add(new WeatherForecastPoint(
                        (decimal)response.Hourly.Temperature2m[i],
                        timestamp));
                }
            }

            logger.LogInformation("Fetched {Count} forecast points from Open-Meteo", points.Count);
            return new WeatherForecast(points, fetchedAt);
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "Failed to fetch weather forecast from Open-Meteo");
            return null;
        }
    }

    private sealed class OpenMeteoResponse
    {
        [JsonPropertyName("hourly")]
        public HourlyData? Hourly { get; set; }
    }

    private sealed class HourlyData
    {
        [JsonPropertyName("time")]
        public List<string> Time { get; set; } = [];

        [JsonPropertyName("temperature_2m")]
        public List<double> Temperature2m { get; set; } = [];
    }
}
