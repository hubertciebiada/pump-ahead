using Microsoft.Extensions.DependencyInjection;

namespace PumpAhead.Adapters.Web;

public static class ServiceCollectionExtensions
{
    public static IServiceCollection AddPumpAheadWeb(
        this IServiceCollection services,
        Action<WebOptions> configure)
    {
        services.Configure(configure);
        return services;
    }
}
