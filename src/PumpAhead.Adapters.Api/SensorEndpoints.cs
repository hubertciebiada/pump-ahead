using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Routing;
using Microsoft.Extensions.Logging;
using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.UseCases.Commands.RecordSensorReading;
using PumpAhead.UseCases.Ports;

namespace PumpAhead.Adapters.Api;

public static class SensorEndpoints
{
    public static IEndpointRouteBuilder MapSensorEndpoints(this IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("/api/sensors");

        group.MapGet("/{sensorId}/readings", RecordReadingFromQuery)
            .WithName("RecordSensorReadingGet");

        return app;
    }

    private static async Task<IResult> RecordReadingFromQuery(
        string sensorId,
        decimal tC,
        ICommandHandler<RecordSensorReading.Command> handler,
        ILoggerFactory loggerFactory,
        CancellationToken cancellationToken)
    {
        var logger = loggerFactory.CreateLogger("SensorEndpoints");

        try
        {
            var command = new RecordSensorReading.Command(
                SensorId.From(sensorId),
                Temperature.FromCelsius(tC),
                DateTimeOffset.UtcNow);

            await handler.HandleAsync(command, cancellationToken);

            logger.LogInformation(
                "Recorded reading from sensor {SensorId}: {Temperature}",
                sensorId, tC);

            return Results.Ok(new { status = "ok", sensorId, temperature = tC });
        }
        catch (ArgumentException ex)
        {
            logger.LogWarning(ex, "Invalid request for sensor {SensorId}", sensorId);
            return Results.BadRequest(new { error = ex.Message });
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "Failed to record reading for sensor {SensorId}", sensorId);
            return Results.Problem("Failed to record sensor reading");
        }
    }
}
