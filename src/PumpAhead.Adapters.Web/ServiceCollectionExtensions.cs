using Microsoft.Extensions.DependencyInjection;
using PumpAhead.Adapters.Web.Services;
using Radzen;

namespace PumpAhead.Adapters.Web;

public static class ServiceCollectionExtensions
{
    public static IServiceCollection AddPumpAheadWeb(
        this IServiceCollection services,
        Action<WebOptions> configure)
    {
        services.Configure(configure);
        services.AddRadzenComponents();
        services.AddScoped<RefreshService>();
        return services;
    }
}
