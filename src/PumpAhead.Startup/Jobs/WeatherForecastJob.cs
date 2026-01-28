using Microsoft.AspNetCore.SignalR;
using PumpAhead.Adapters.Gui.Hubs;
using PumpAhead.Adapters.Gui.Services;
using PumpAhead.UseCases.Ports.Out;
using Quartz;

namespace PumpAhead.Startup.Jobs;

[DisallowConcurrentExecution]
public sealed class WeatherForecastJob(
    IWeatherForecastProvider weatherProvider,
    IWeatherForecastRepository weatherRepository,
    IHubContext<SensorHub, ISensorHubClient> hubContext,
    Microsoft.Extensions.Options.IOptions<WeatherSettings> settings,
    ILogger<WeatherForecastJob> logger) : IJob
{
    public static readonly JobKey Key = new("weather-forecast", "polling");

    public async Task Execute(IJobExecutionContext context)
    {
        try
        {
            var config = settings.Value;
            var forecast = await weatherProvider.GetForecastAsync(
                config.Latitude, config.Longitude, config.ForecastHours, context.CancellationToken);

            if (forecast is { HourlyPoints.Count: > 0 })
            {
                await weatherRepository.SaveForecastAsync(
                    forecast.HourlyPoints, forecast.FetchedAt, context.CancellationToken);
                await hubContext.Clients.All.ReceiveWeatherForecastUpdate();
                logger.LogInformation("Weather forecast updated: {Count} points", forecast.HourlyPoints.Count);
            }
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "Failed to update weather forecast");
        }
    }
}
