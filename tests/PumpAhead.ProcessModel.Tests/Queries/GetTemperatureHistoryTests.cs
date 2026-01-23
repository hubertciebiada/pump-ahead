using NSubstitute;
using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.UseCases.Ports.Out;
using PumpAhead.UseCases.Queries.GetTemperatureHistory;

namespace PumpAhead.ProcessModel.Tests.Queries;

public class GetTemperatureHistoryTests
{
    private readonly ITemperatureRepository _repository;
    private readonly GetTemperatureHistory.Handler _handler;

    public GetTemperatureHistoryTests()
    {
        _repository = Substitute.For<ITemperatureRepository>();
        _handler = new GetTemperatureHistory.Handler(_repository);
    }

    [Fact]
    public async Task HandleAsync_ReturnsEmptyData_WhenNoReadings()
    {
        var sensorId = SensorId.New();
        var from = DateTimeOffset.UtcNow.AddHours(-24);
        var to = DateTimeOffset.UtcNow;

        _repository
            .GetHistoryAsync(sensorId, from, to, Arg.Any<CancellationToken>())
            .Returns(new List<TemperatureReading>());

        var result = await _handler.HandleAsync(new GetTemperatureHistory.Query(sensorId, from, to));

        Assert.Empty(result.Readings);
    }

    [Fact]
    public async Task HandleAsync_ReturnsReadings_WhenDataExists()
    {
        var sensorId = SensorId.New();
        var from = DateTimeOffset.UtcNow.AddHours(-24);
        var to = DateTimeOffset.UtcNow;

        var readings = new List<TemperatureReading>
        {
            new(sensorId, Temperature.FromCelsius(20m), from.AddHours(1)),
            new(sensorId, Temperature.FromCelsius(21m), from.AddHours(2)),
            new(sensorId, Temperature.FromCelsius(22m), from.AddHours(3))
        };

        _repository
            .GetHistoryAsync(sensorId, from, to, Arg.Any<CancellationToken>())
            .Returns(readings);

        var result = await _handler.HandleAsync(new GetTemperatureHistory.Query(sensorId, from, to));

        Assert.Equal(3, result.Readings.Count);
        Assert.Equal(20m, result.Readings[0].Temperature.Celsius);
        Assert.Equal(21m, result.Readings[1].Temperature.Celsius);
        Assert.Equal(22m, result.Readings[2].Temperature.Celsius);
    }

    [Fact]
    public async Task HandleAsync_PreservesTimestamps()
    {
        var sensorId = SensorId.New();
        var from = DateTimeOffset.UtcNow.AddHours(-24);
        var to = DateTimeOffset.UtcNow;
        var timestamp1 = from.AddHours(1);
        var timestamp2 = from.AddHours(2);

        var readings = new List<TemperatureReading>
        {
            new(sensorId, Temperature.FromCelsius(20m), timestamp1),
            new(sensorId, Temperature.FromCelsius(21m), timestamp2)
        };

        _repository
            .GetHistoryAsync(sensorId, from, to, Arg.Any<CancellationToken>())
            .Returns(readings);

        var result = await _handler.HandleAsync(new GetTemperatureHistory.Query(sensorId, from, to));

        Assert.Equal(timestamp1, result.Readings[0].Timestamp);
        Assert.Equal(timestamp2, result.Readings[1].Timestamp);
    }
}
