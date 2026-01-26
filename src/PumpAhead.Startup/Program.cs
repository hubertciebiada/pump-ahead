using PumpAhead.Adapters.Web;
using PumpAhead.Adapters.Web.Components;
using PumpAhead.Startup.Api;
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

    var webSettings = builder.Configuration.GetSection("Web").Get<WebOptions>() ?? new WebOptions();
    builder.Services.AddPumpAheadWeb(options =>
    {
        options.DefaultSensorId = webSettings.DefaultSensorId;
        options.ForecastOffsetHours = webSettings.ForecastOffsetHours;
        options.TargetIndoorTemperature = webSettings.TargetIndoorTemperature;
    });

    builder.Services.AddRazorComponents()
        .AddInteractiveServerComponents();

    var app = builder.Build();

    if (!app.Environment.IsDevelopment())
    {
        app.UseExceptionHandler("/Error", createScopeForErrors: true);
        app.UseHsts();
    }

    app.UseAntiforgery();

    app.MapStaticAssets();
    
    app.MapRazorComponents<App>().AddInteractiveServerRenderMode();
    app.MapSensorEndpoints();

    Log.Information("PumpAhead starting up on port 1488");
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
