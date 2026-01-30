using FluentAssertions;
using NSubstitute;
using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.UseCases.Ports.Out;
using PumpAhead.UseCases.Queries.GetTemperature;

namespace PumpAhead.ProcessModel.Tests.Queries;

public class GetTemperatureTests
{
    private const string TestSensorId1 = "test-sensor-1";
    private const string NonExistentSensorId = "non-existent-sensor";
    private const string SensorWithoutReadingsId = "sensor-without-readings";
    private const string TestSensorForVerificationId = "test-sensor-for-verification";
    private const string FreezerSensorId = "freezer-sensor";
    private const string TestSensorId = "test-sensor";
    private const decimal DefaultTemperatureCelsius = 21.5m;
    private const decimal NegativeTemperatureCelsius = -18.5m;

    private readonly ITemperatureRepository _repository;
    private readonly GetTemperature.Handler _handler;

    public GetTemperatureTests()
    {
        _repository = Substitute.For<ITemperatureRepository>();
        _handler = new GetTemperature.Handler(_repository);
    }

    [Fact]
    public async Task HandleAsync_WhenSensorHasReading_ShouldReturnTemperatureData()
    {
        // Given
        var sensorId = SensorId.From(TestSensorId1);
        var temperature = Temperature.FromCelsius(DefaultTemperatureCelsius);
        var timestamp = DateTimeOffset.UtcNow;

        _repository
            .GetLatestAsync(sensorId, Arg.Any<CancellationToken>())
            .Returns(new SensorReading(sensorId, temperature, timestamp));

        // When
        var result = await _handler.HandleAsync(new GetTemperature.Query(sensorId));

        // Then
        result.Should().NotBeNull();
        result!.Temperature.Should().Be(temperature);
        result.Timestamp.Should().Be(timestamp);
    }

    [Fact]
    public async Task HandleAsync_WhenSensorDoesNotExist_ShouldReturnNull()
    {
        // Given
        var sensorId = SensorId.From(NonExistentSensorId);

        _repository
            .GetLatestAsync(sensorId, Arg.Any<CancellationToken>())
            .Returns((SensorReading?)null);

        // When
        var result = await _handler.HandleAsync(new GetTemperature.Query(sensorId));

        // Then
        result.Should().BeNull();
    }

    [Fact]
    public async Task HandleAsync_WhenSensorHasNoReadings_ShouldReturnNull()
    {
        // Given
        var sensorId = SensorId.From(SensorWithoutReadingsId);

        _repository
            .GetLatestAsync(sensorId, Arg.Any<CancellationToken>())
            .Returns((SensorReading?)null);

        // When
        var result = await _handler.HandleAsync(new GetTemperature.Query(sensorId));

        // Then
        result.Should().BeNull();
    }

    [Fact]
    public async Task HandleAsync_ShouldCallRepositoryWithCorrectSensorId()
    {
        // Given
        var sensorId = SensorId.From(TestSensorForVerificationId);

        _repository
            .GetLatestAsync(Arg.Any<SensorId>(), Arg.Any<CancellationToken>())
            .Returns((SensorReading?)null);

        // When
        await _handler.HandleAsync(new GetTemperature.Query(sensorId));

        // Then
        await _repository.Received(1).GetLatestAsync(sensorId, Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task HandleAsync_WhenTemperatureIsNegative_ShouldReturnCorrectValue()
    {
        // Given
        var sensorId = SensorId.From(FreezerSensorId);
        var temperature = Temperature.FromCelsius(NegativeTemperatureCelsius);
        var timestamp = DateTimeOffset.UtcNow;

        _repository
            .GetLatestAsync(sensorId, Arg.Any<CancellationToken>())
            .Returns(new SensorReading(sensorId, temperature, timestamp));

        // When
        var result = await _handler.HandleAsync(new GetTemperature.Query(sensorId));

        // Then
        result.Should().NotBeNull();
        result!.Temperature.Celsius.Should().Be(NegativeTemperatureCelsius);
    }

    [Fact]
    public async Task HandleAsync_ShouldPassCancellationToken()
    {
        // Given
        var sensorId = SensorId.From(TestSensorId);
        var cancellationToken = new CancellationToken();

        _repository
            .GetLatestAsync(sensorId, cancellationToken)
            .Returns((SensorReading?)null);

        // When
        await _handler.HandleAsync(new GetTemperature.Query(sensorId), cancellationToken);

        // Then
        await _repository.Received(1).GetLatestAsync(sensorId, cancellationToken);
    }
}
