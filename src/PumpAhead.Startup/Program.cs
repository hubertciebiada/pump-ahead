using PumpAhead.Adapters.Web;
using PumpAhead.Adapters.Web.Components;
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

    var deviceSettings = builder.Configuration.GetSection("Devices").Get<DeviceSettings>() ?? new();

    builder.Services.Configure<DeviceSettings>(builder.Configuration.GetSection("Devices"));
    builder.Services.Configure<PollingSettings>(builder.Configuration.GetSection("Polling"));

    builder.Services.AddAdapters(builder.Configuration);
    builder.Services.AddUseCases();
    builder.Services.AddQuartzJobs(builder.Configuration);

    builder.Services.AddPumpAheadWeb(options =>
    {
        options.DefaultSensorId = deviceSettings.Shelly.SensorId;
    });

    builder.Services.AddRazorComponents()
        .AddInteractiveServerComponents();

    var app = builder.Build();

    if (!app.Environment.IsDevelopment())
    {
        app.UseExceptionHandler("/Error", createScopeForErrors: true);
        app.UseHsts();
    }

    app.UseHttpsRedirection();
    app.UseAntiforgery();

    app.MapStaticAssets();
    app.MapRazorComponents<App>()
        .AddInteractiveServerRenderMode();

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
