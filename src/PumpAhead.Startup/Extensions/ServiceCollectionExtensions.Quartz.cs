using PumpAhead.Startup.Configuration;
using PumpAhead.Startup.Jobs;
using Quartz;

namespace PumpAhead.Startup.Extensions;

public static partial class ServiceCollectionExtensions
{
    public static IServiceCollection AddQuartzJobs(
        this IServiceCollection services,
        IConfiguration configuration)
    {
        var pollingSettings = configuration.GetSection("Polling").Get<PollingSettings>() ?? new PollingSettings();

        services.AddQuartz(q =>
        {
            var shellyJobKey = new JobKey("ShellyPollingJob");
            q.AddJob<ShellyPollingJob>(opts => opts.WithIdentity(shellyJobKey));
            q.AddTrigger(opts => opts
                .ForJob(shellyJobKey)
                .WithIdentity("ShellyPollingJob-trigger")
                .WithSimpleSchedule(x => x
                    .WithIntervalInMinutes(pollingSettings.ShellyIntervalMinutes)
                    .RepeatForever())
                .StartNow());
        });

        services.AddQuartzHostedService(q => q.WaitForJobsToComplete = true);

        return services;
    }
}
