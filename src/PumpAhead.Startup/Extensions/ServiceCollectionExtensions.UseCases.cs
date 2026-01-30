using PumpAhead.UseCases.Commands.RecordSensorReading;
using PumpAhead.UseCases.Commands.SaveHeatPumpSnapshot;
using PumpAhead.UseCases.Commands.SaveTemperature;
using PumpAhead.UseCases.Commands.SyncHeatPumpState;
using PumpAhead.UseCases.Ports;
using PumpAhead.UseCases.Queries.GetAllSensorsHistory;
using PumpAhead.UseCases.Queries.GetHeatPumpHistory;
using PumpAhead.UseCases.Queries.GetHeatPumpStatus;
using PumpAhead.UseCases.Queries.GetTemperature;
using PumpAhead.UseCases.Queries.GetTemperatureHistory;
using PumpAhead.UseCases.Queries.GetWeatherForecast;

namespace PumpAhead.Startup.Extensions;

public static partial class ServiceCollectionExtensions
{
    public static IServiceCollection AddUseCases(this IServiceCollection services)
    {
        // Temperature commands
        services.AddScoped<ICommandHandler<SaveTemperature.Command>, SaveTemperature.Handler>();
        services.AddScoped<ICommandHandler<RecordSensorReading.Command>, RecordSensorReading.Handler>();

        // HeatPump commands
        services.AddScoped<ICommandHandler<SyncHeatPumpState.Command>, SyncHeatPumpState.Handler>();
        services.AddScoped<ICommandHandler<SaveHeatPumpSnapshot.Command>, SaveHeatPumpSnapshot.Handler>();

        // Temperature queries
        services.AddScoped<IQueryHandler<GetTemperature.Query, GetTemperature.Data?>, GetTemperature.Handler>();
        services.AddScoped<IQueryHandler<GetTemperatureHistory.Query, GetTemperatureHistory.Data>, GetTemperatureHistory.Handler>();
        services.AddScoped<IQueryHandler<GetAllSensorsHistory.Query, GetAllSensorsHistory.Data>, GetAllSensorsHistory.Handler>();
        services.AddScoped<IQueryHandler<GetWeatherForecast.Query, GetWeatherForecast.Data>, GetWeatherForecast.Handler>();

        // HeatPump queries
        services.AddScoped<IQueryHandler<GetHeatPumpStatus.Query, GetHeatPumpStatus.Data?>, GetHeatPumpStatus.Handler>();
        services.AddScoped<IQueryHandler<GetHeatPumpHistory.Query, GetHeatPumpHistory.Data>, GetHeatPumpHistory.Handler>();

        return services;
    }
}
