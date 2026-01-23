using PumpAhead.UseCases.Commands.SaveTemperature;
using PumpAhead.UseCases.Ports;
using PumpAhead.UseCases.Queries.GetTemperature;
using PumpAhead.UseCases.Queries.GetTemperatureHistory;

namespace PumpAhead.Startup.Extensions;

public static partial class ServiceCollectionExtensions
{
    public static IServiceCollection AddUseCases(this IServiceCollection services)
    {
        services.AddScoped<ICommandHandler<SaveTemperature.Command>, SaveTemperature.Handler>();
        services.AddScoped<IQueryHandler<GetTemperature.Query, GetTemperature.Data?>, GetTemperature.Handler>();
        services.AddScoped<IQueryHandler<GetTemperatureHistory.Query, GetTemperatureHistory.Data>, GetTemperatureHistory.Handler>();

        return services;
    }
}
