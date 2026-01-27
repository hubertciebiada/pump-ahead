using PumpAhead.Adapters.Api;
using PumpAhead.Adapters.Gui;
using PumpAhead.Startup.Configuration;
using PumpAhead.Startup.Extensions;
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
    builder.Services.AddGui();

    var app = builder.Build();

    app.UseAntiforgery();

    app.MapStaticAssets();
    app.MapSensorEndpoints();
    app.MapGui();

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
