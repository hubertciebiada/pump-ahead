using Microsoft.EntityFrameworkCore;
using PumpAhead.Adapters.Gui.Services;
using PumpAhead.Adapters.Out.HeishaMon;
using PumpAhead.Adapters.Out.Persistence.SqlServer;
using PumpAhead.Adapters.Out.Persistence.SqlServer.Repositories;
using PumpAhead.Adapters.Out.Weather;
using PumpAhead.Startup.Configuration;
using PumpAhead.UseCases.Ports.Out;

namespace PumpAhead.Startup.Extensions;

public static partial class ServiceCollectionExtensions
{
    public static IServiceCollection AddAdapters(
        this IServiceCollection services,
        IConfiguration configuration)
    {
        services.AddDbContext<PumpAheadDbContext>(options =>
            options.UseSqlServer(configuration.GetConnectionString("DefaultConnection")));

        services.AddScoped<ITemperatureRepository, SqlServerTemperatureRepository>();
        services.AddScoped<ISensorRepository, SqlServerSensorRepository>();
        services.AddScoped<IHeatPumpRepository, SqlServerHeatPumpRepository>();
        services.AddScoped<IHeatPumpSnapshotRepository, SqlServerHeatPumpSnapshotRepository>();
        services.AddScoped<IWeatherForecastRepository, SqlServerWeatherForecastRepository>();

        services.AddHttpClient<IWeatherForecastProvider, OpenMeteoWeatherProvider>();

        // HeishaMon HTTP client with configured base address and timeout
        services.AddHttpClient<IHeishaMonProvider, HeishaMonProvider>((sp, client) =>
        {
            var settings = configuration.GetSection("Devices:Heishamon").Get<HeishaMonSettings>()
                ?? new HeishaMonSettings();
            client.BaseAddress = new Uri(settings.Address);
            client.Timeout = TimeSpan.FromSeconds(settings.TimeoutSeconds);
        });

        // Notification services
        services.AddScoped<IHeatPumpNotificationService, SignalRHeatPumpNotificationService>();

        return services;
    }
}
