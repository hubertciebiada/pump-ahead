using FluentAssertions;
using NSubstitute;
using NSubstitute.ExceptionExtensions;
using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.UseCases.Commands.SaveTemperature;
using PumpAhead.UseCases.Ports.Out;

namespace PumpAhead.ProcessModel.Tests.Commands;

public class SaveTemperatureTests
{
    private const string TestSensorId1 = "test-sensor-1";
    private const string TestSensorId2 = "test-sensor-2";
    private const string TestSensorId = "test-sensor";
    private const string FreezerSensorId = "freezer-sensor";
    private const string MultiReadingSensorId = "multi-reading-sensor";
    private const string ZeroTempSensorId = "zero-temp-sensor";
    private const string DatabaseErrorMessage = "Database error";
    private const decimal DefaultTemperatureCelsius = 21.5m;
    private const decimal NegativeTemperatureCelsius = -18.5m;
    private const decimal ZeroTemperatureCelsius = 0m;
    private const decimal RoomTemperatureCelsius = 20.0m;
    private const decimal SlightlyHigherTemperatureCelsius = 21.0m;
    private const int MultipleReadingsDelayMinutes = 5;

    private readonly ITemperatureRepository _repository;
    private readonly SaveTemperature.Handler _handler;

    public SaveTemperatureTests()
    {
        _repository = Substitute.For<ITemperatureRepository>();
        _handler = new SaveTemperature.Handler(_repository);
    }

    [Fact]
    public async Task HandleAsync_WhenValidCommand_ShouldSaveTemperatureReading()
    {
        // Given
        var sensorId = SensorId.From(TestSensorId1);
        var temperature = Temperature.FromCelsius(DefaultTemperatureCelsius);
        var timestamp = DateTimeOffset.UtcNow;
        var command = new SaveTemperature.Command(sensorId, temperature, timestamp);

        // When
        await _handler.HandleAsync(command);

        // Then
        await _repository.Received(1).SaveAsync(
            Arg.Is<SensorReading>(r =>
                r.SensorId == sensorId &&
                r.Temperature == temperature &&
                r.Timestamp == timestamp),
            Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task HandleAsync_WhenRepositoryThrows_ShouldPropagateException()
    {
        // Given
        var sensorId = SensorId.From(TestSensorId2);
        var command = new SaveTemperature.Command(
            sensorId,
            Temperature.FromCelsius(DefaultTemperatureCelsius),
            DateTimeOffset.UtcNow);

        _repository
            .SaveAsync(Arg.Any<SensorReading>(), Arg.Any<CancellationToken>())
            .ThrowsAsync(new InvalidOperationException(DatabaseErrorMessage));

        // When
        var act = () => _handler.HandleAsync(command);

        // Then
        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage(DatabaseErrorMessage);
    }

    [Fact]
    public async Task HandleAsync_WhenNegativeTemperature_ShouldSaveCorrectly()
    {
        // Given
        var sensorId = SensorId.From(FreezerSensorId);
        var temperature = Temperature.FromCelsius(NegativeTemperatureCelsius);
        var timestamp = DateTimeOffset.UtcNow;
        var command = new SaveTemperature.Command(sensorId, temperature, timestamp);

        // When
        await _handler.HandleAsync(command);

        // Then
        await _repository.Received(1).SaveAsync(
            Arg.Is<SensorReading>(r => r.Temperature.Celsius == NegativeTemperatureCelsius),
            Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task HandleAsync_ShouldPassCancellationToken()
    {
        // Given
        var sensorId = SensorId.From(TestSensorId);
        var command = new SaveTemperature.Command(
            sensorId,
            Temperature.FromCelsius(RoomTemperatureCelsius),
            DateTimeOffset.UtcNow);
        using var cts = new CancellationTokenSource();
        var cancellationToken = cts.Token;

        // When
        await _handler.HandleAsync(command, cancellationToken);

        // Then
        await _repository.Received(1).SaveAsync(
            Arg.Any<SensorReading>(),
            cancellationToken);
    }

    [Fact]
    public async Task HandleAsync_WhenMultipleCommandsForSameSensor_ShouldSaveEachReading()
    {
        // Given
        var sensorId = SensorId.From(MultiReadingSensorId);
        var timestamp1 = DateTimeOffset.UtcNow;
        var timestamp2 = timestamp1.AddMinutes(MultipleReadingsDelayMinutes);
        var command1 = new SaveTemperature.Command(sensorId, Temperature.FromCelsius(RoomTemperatureCelsius), timestamp1);
        var command2 = new SaveTemperature.Command(sensorId, Temperature.FromCelsius(SlightlyHigherTemperatureCelsius), timestamp2);

        // When
        await _handler.HandleAsync(command1);
        await _handler.HandleAsync(command2);

        // Then
        await _repository.Received(2).SaveAsync(
            Arg.Any<SensorReading>(),
            Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task HandleAsync_WhenZeroTemperature_ShouldSaveCorrectly()
    {
        // Given
        var sensorId = SensorId.From(ZeroTempSensorId);
        var temperature = Temperature.FromCelsius(ZeroTemperatureCelsius);
        var timestamp = DateTimeOffset.UtcNow;
        var command = new SaveTemperature.Command(sensorId, temperature, timestamp);

        // When
        await _handler.HandleAsync(command);

        // Then
        await _repository.Received(1).SaveAsync(
            Arg.Is<SensorReading>(r => r.Temperature.Celsius == ZeroTemperatureCelsius),
            Arg.Any<CancellationToken>());
    }
}
