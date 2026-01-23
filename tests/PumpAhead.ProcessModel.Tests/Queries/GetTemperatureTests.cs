using NSubstitute;
using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.UseCases.Ports.Out;
using PumpAhead.UseCases.Queries.GetTemperature;

namespace PumpAhead.ProcessModel.Tests.Queries;

public class GetTemperatureTests
{
    private readonly ITemperatureRepository _repository;
    private readonly GetTemperature.Handler _handler;

    public GetTemperatureTests()
    {
        _repository = Substitute.For<ITemperatureRepository>();
        _handler = new GetTemperature.Handler(_repository);
    }

    [Fact]
    public async Task HandleAsync_ReturnsData_WhenReadingExists()
    {
        var sensorId = SensorId.New();
        var temperature = Temperature.FromCelsius(21.5m);
        var timestamp = DateTimeOffset.UtcNow;

        _repository
            .GetLatestAsync(sensorId, Arg.Any<CancellationToken>())
            .Returns(new TemperatureReading(sensorId, temperature, timestamp));

        var result = await _handler.HandleAsync(new GetTemperature.Query(sensorId));

        Assert.NotNull(result);
        Assert.Equal(temperature, result.Temperature);
        Assert.Equal(timestamp, result.Timestamp);
    }

    [Fact]
    public async Task HandleAsync_ReturnsNull_WhenNoReadingExists()
    {
        var sensorId = SensorId.New();

        _repository
            .GetLatestAsync(sensorId, Arg.Any<CancellationToken>())
            .Returns((TemperatureReading?)null);

        var result = await _handler.HandleAsync(new GetTemperature.Query(sensorId));

        Assert.Null(result);
    }
}
