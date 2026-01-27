using Microsoft.EntityFrameworkCore;
using PumpAhead.Adapters.Out.Persistence.SqlServer;
using PumpAhead.Adapters.Out.Persistence.SqlServer.Repositories;
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

        return services;
    }
}
