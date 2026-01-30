using PumpAhead.Startup.Configuration;
using PumpAhead.Startup.Jobs;
using Quartz;

namespace PumpAhead.Startup.Extensions;

public static partial class ServiceCollectionExtensions
{
    public static IServiceCollection AddScheduler(
        this IServiceCollection services,
        IConfiguration configuration)
    {
        var heishaMonSettings = configuration.GetSection("Devices:Heishamon").Get<HeishaMonSettings>()
            ?? new HeishaMonSettings();

        services.AddQuartz(q =>
        {
            q.UseInMemoryStore();

            // Weather forecast job - every 15 minutes
            q.AddJob<WeatherForecastJob>(j => j
                .WithIdentity(WeatherForecastJob.Key)
                .StoreDurably());

            q.AddTrigger(t => t
                .ForJob(WeatherForecastJob.Key)
                .WithIdentity("weather-forecast-trigger", "polling")
                .StartNow()
                .WithSimpleSchedule(s => s
                    .WithIntervalInMinutes(15)
                    .RepeatForever()));

            // // HeishaMon polling job - configurable interval (default 30 seconds)
            // q.AddJob<HeishaMonPollingJob>(j => j
            //     .WithIdentity(HeishaMonPollingJob.Key)
            //     .StoreDurably());
            //
            // q.AddTrigger(t => t
            //     .ForJob(HeishaMonPollingJob.Key)
            //     .WithIdentity("heishamon-polling-trigger", "polling")
            //     .StartNow()
            //     .WithSimpleSchedule(s => s
            //         .WithIntervalInSeconds(heishaMonSettings.PollingIntervalSeconds)
            //         .RepeatForever()));
        });

        services.AddQuartzHostedService(q => q.WaitForJobsToComplete = true);

        return services;
    }
}
