using PumpAhead.UseCases.Commands.RecordSensorReading;
using PumpAhead.UseCases.Commands.SaveTemperature;
using PumpAhead.UseCases.Ports;
using PumpAhead.UseCases.Queries.GetAllSensorsHistory;
using PumpAhead.UseCases.Queries.GetTemperature;
using PumpAhead.UseCases.Queries.GetTemperatureHistory;
using PumpAhead.UseCases.Queries.GetWeatherForecast;

namespace PumpAhead.Startup.Extensions;

public static partial class ServiceCollectionExtensions
{
    public static IServiceCollection AddUseCases(this IServiceCollection services)
    {
        services.AddScoped<ICommandHandler<SaveTemperature.Command>, SaveTemperature.Handler>();
        services.AddScoped<ICommandHandler<RecordSensorReading.Command>, RecordSensorReading.Handler>();
        services.AddScoped<IQueryHandler<GetTemperature.Query, GetTemperature.Data?>, GetTemperature.Handler>();
        services.AddScoped<IQueryHandler<GetTemperatureHistory.Query, GetTemperatureHistory.Data>, GetTemperatureHistory.Handler>();
        services.AddScoped<IQueryHandler<GetAllSensorsHistory.Query, GetAllSensorsHistory.Data>, GetAllSensorsHistory.Handler>();
        services.AddScoped<IQueryHandler<GetWeatherForecast.Query, GetWeatherForecast.Data>, GetWeatherForecast.Handler>();

        return services;
    }
}
