using Microsoft.AspNetCore.Builder;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using PumpAhead.Adapters.Gui.Hubs;
using PumpAhead.Adapters.Gui.Services;
using PumpAhead.UseCases.Ports.Out;
using Radzen;

namespace PumpAhead.Adapters.Gui;

public static class GuiExtensions
{
    public static IServiceCollection AddGui(this IServiceCollection services, IConfiguration configuration)
    {
        services.Configure<WeatherSettings>(configuration.GetSection("Weather"));
        services.AddRazorComponents()
            .AddInteractiveServerComponents();
        services.AddRadzenComponents();
        services.AddSignalR();
        services.AddScoped<LightweightChartsService>();
        services.AddScoped<ISensorNotificationService, SignalRSensorNotificationService>();

        return services;
    }

    public static WebApplication MapGui(this WebApplication app)
    {
        app.MapRazorComponents<App>()
            .AddInteractiveServerRenderMode();
        app.MapHub<SensorHub>("/hubs/sensors");

        return app;
    }
}
