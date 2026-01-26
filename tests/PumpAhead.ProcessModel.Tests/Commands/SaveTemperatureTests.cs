using NSubstitute;
using NSubstitute.ExceptionExtensions;
using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.UseCases.Commands.SaveTemperature;
using PumpAhead.UseCases.Ports.Out;

namespace PumpAhead.ProcessModel.Tests.Commands;

public class SaveTemperatureTests
{
    private readonly ITemperatureRepository _repository;
    private readonly SaveTemperature.Handler _handler;

    public SaveTemperatureTests()
    {
        _repository = Substitute.For<ITemperatureRepository>();
        _handler = new SaveTemperature.Handler(_repository);
    }

    [Fact]
    public async Task HandleAsync_SavesTemperatureReading()
    {
        var sensorId = SensorId.From("test-sensor-1");
        var temperature = Temperature.FromCelsius(21.5m);
        var timestamp = DateTimeOffset.UtcNow;

        var command = new SaveTemperature.Command(sensorId, temperature, timestamp);

        await _handler.HandleAsync(command);

        await _repository.Received(1).SaveAsync(
            Arg.Is<SensorReading>(r =>
                r.SensorId == sensorId &&
                r.Temperature == temperature &&
                r.Timestamp == timestamp),
            Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task HandleAsync_PropagatesRepositoryException()
    {
        var sensorId = SensorId.From("test-sensor-2");
        var command = new SaveTemperature.Command(
            sensorId,
            Temperature.FromCelsius(21.5m),
            DateTimeOffset.UtcNow);

        _repository
            .SaveAsync(Arg.Any<SensorReading>(), Arg.Any<CancellationToken>())
            .ThrowsAsync(new InvalidOperationException("Database error"));

        await Assert.ThrowsAsync<InvalidOperationException>(
            () => _handler.HandleAsync(command));
    }
}
