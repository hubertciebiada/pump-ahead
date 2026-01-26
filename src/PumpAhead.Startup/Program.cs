using PumpAhead.Adapters.Api;
using PumpAhead.Startup.Configuration;
using PumpAhead.Startup.Extensions;
using PumpAhead.Startup.Hubs;
using Serilog;

Log.Logger = new LoggerConfiguration()
    .WriteTo.Console()
    .CreateBootstrapLogger();

try
{
    var builder = WebApplication.CreateBuilder(args);

    builder.Host.AddSerilog();

    builder.Services.Configure<PollingSettings>(builder.Configuration.GetSection("Polling"));

    builder.Services.AddAdapters(builder.Configuration);
    builder.Services.AddUseCases();
    builder.Services.AddBlazor();

    var app = builder.Build();

    app.UseStaticFiles();
    app.UseRouting();

    app.MapSensorEndpoints();
    app.MapBlazorHub();
    app.MapHub<SensorHub>("/hubs/sensors");
    app.MapFallbackToPage("/_Host");

    Log.Information("PumpAhead starting up");
    app.Run();
}
catch (Exception ex)
{
    Log.Fatal(ex, "Application terminated unexpectedly");
}
finally
{
    Log.CloseAndFlush();
}
