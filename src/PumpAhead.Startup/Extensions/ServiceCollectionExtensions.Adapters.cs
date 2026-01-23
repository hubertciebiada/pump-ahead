using Microsoft.EntityFrameworkCore;
using PumpAhead.Adapters.Out.Persistence.SqlServer;
using PumpAhead.Adapters.Out.Persistence.SqlServer.Repositories;
using PumpAhead.Adapters.Out.Sensors.Shelly;
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

        var deviceSettings = configuration.GetSection("Devices").Get<DeviceSettings>() ?? new DeviceSettings();

        services.AddHttpClient<ISensorReader, ShellySensorReader>(client =>
        {
            client.BaseAddress = new Uri(deviceSettings.Shelly.Address);
            client.Timeout = TimeSpan.FromSeconds(30);
        });

        return services;
    }
}
