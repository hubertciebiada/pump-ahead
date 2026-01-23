using Microsoft.Extensions.DependencyInjection;
using MudBlazor.Services;

namespace PumpAhead.Adapters.Web;

public static class ServiceCollectionExtensions
{
    public static IServiceCollection AddPumpAheadWeb(
        this IServiceCollection services,
        Action<WebOptions> configure)
    {
        services.Configure(configure);
        services.AddMudServices();
        return services;
    }
}
