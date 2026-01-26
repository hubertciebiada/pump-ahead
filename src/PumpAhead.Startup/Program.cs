using PumpAhead.Adapters.Api;
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

    var app = builder.Build();

    app.MapSensorEndpoints();

    Log.Information("PumpAhead API starting up");
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
