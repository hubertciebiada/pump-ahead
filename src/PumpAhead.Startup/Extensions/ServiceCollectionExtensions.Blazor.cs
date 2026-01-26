using PumpAhead.Startup.Hubs;
using PumpAhead.Startup.Services;
using PumpAhead.UseCases.Ports.Out;
using Radzen;

namespace PumpAhead.Startup.Extensions;

public static partial class ServiceCollectionExtensions
{
    public static IServiceCollection AddBlazor(this IServiceCollection services)
    {
        services.AddRazorPages();
        services.AddServerSideBlazor();
        services.AddRadzenComponents();
        services.AddSignalR();
        services.AddScoped<LightweightChartsService>();
        services.AddScoped<ChartStateService>();
        services.AddScoped<ISensorNotificationService, SignalRSensorNotificationService>();

        return services;
    }
}
