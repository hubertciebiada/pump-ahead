using PumpAhead.Startup.Jobs;
using Quartz;

namespace PumpAhead.Startup.Extensions;

public static partial class ServiceCollectionExtensions
{
    public static IServiceCollection AddScheduler(this IServiceCollection services)
    {
        services.AddQuartz(q =>
        {
            q.UseInMemoryStore();

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
        });

        services.AddQuartzHostedService(q => q.WaitForJobsToComplete = true);

        return services;
    }
}
