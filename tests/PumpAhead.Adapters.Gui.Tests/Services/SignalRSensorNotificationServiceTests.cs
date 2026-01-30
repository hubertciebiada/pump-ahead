using FluentAssertions;
using Microsoft.AspNetCore.SignalR;
using NSubstitute;
using PumpAhead.Adapters.Gui.Hubs;
using PumpAhead.Adapters.Gui.Services;
using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.Adapters.Gui.Tests.Services;

public class SignalRSensorNotificationServiceTests
{
    private const string Sensor1Id = "sensor-1";
    private const string Sensor2Id = "sensor-2";
    private const string FreezerSensorId = "freezer-sensor";
    private const string PreciseSensorId = "precise-sensor";
    private const string TestSensorId = "test-sensor";
    private const string ExtremeSensorId = "extreme-sensor";

    private const decimal RoomTemperatureCelsius = 22.5m;
    private const decimal FreezerTemperatureCelsius = -18.0m;
    private const decimal PreciseTemperatureCelsius = 21.123456789m;
    private const decimal StandardTemperatureCelsius = 20.0m;
    private const decimal WarmTemperatureCelsius = 25.0m;
    private const decimal AbsoluteZeroCelsius = -273.15m;

    private const long TestUnixTimestamp = 1705315800;
    private const string HubConnectionFailedMessage = "Hub connection failed";

    private static readonly DateTimeOffset TestTimestamp = DateTimeOffset.Parse("2024-01-15T10:30:00Z");

    private readonly IHubContext<SensorHub, ISensorHubClient> _hubContext;
    private readonly ISensorHubClient _allClients;
    private readonly SignalRSensorNotificationService _sut;

    public SignalRSensorNotificationServiceTests()
    {
        _hubContext = Substitute.For<IHubContext<SensorHub, ISensorHubClient>>();
        _allClients = Substitute.For<ISensorHubClient>();
        _hubContext.Clients.All.Returns(_allClients);
        _sut = new SignalRSensorNotificationService(_hubContext);
    }

    [Fact]
    public async Task NotifyReadingRecordedAsync_GivenValidSensorData_WhenInvoked_ThenCallsReceiveSensorUpdateWithCorrectParameters()
    {
        // Given
        var sensorId = SensorId.From(Sensor1Id);
        var temperature = Temperature.FromCelsius(RoomTemperatureCelsius);
        var timestamp = TestTimestamp;

        // When
        await _sut.NotifyReadingRecordedAsync(sensorId, temperature, timestamp);

        // Then
        await _allClients.Received(1).ReceiveSensorUpdate(
            Sensor1Id,
            RoomTemperatureCelsius,
            timestamp.ToUnixTimeSeconds());
    }

    [Fact]
    public async Task NotifyReadingRecordedAsync_GivenNegativeTemperature_WhenInvoked_ThenPassesNegativeValueCorrectly()
    {
        // Given
        var sensorId = SensorId.From(FreezerSensorId);
        var temperature = Temperature.FromCelsius(FreezerTemperatureCelsius);
        var timestamp = DateTimeOffset.UtcNow;

        // When
        await _sut.NotifyReadingRecordedAsync(sensorId, temperature, timestamp);

        // Then
        await _allClients.Received(1).ReceiveSensorUpdate(
            FreezerSensorId,
            FreezerTemperatureCelsius,
            timestamp.ToUnixTimeSeconds());
    }

    [Fact]
    public async Task NotifyReadingRecordedAsync_GivenDecimalPrecision_WhenInvoked_ThenPreservesDecimalValue()
    {
        // Given
        var sensorId = SensorId.From(PreciseSensorId);
        var temperature = Temperature.FromCelsius(PreciseTemperatureCelsius);
        var timestamp = DateTimeOffset.UtcNow;

        // When
        await _sut.NotifyReadingRecordedAsync(sensorId, temperature, timestamp);

        // Then
        await _allClients.Received(1).ReceiveSensorUpdate(
            PreciseSensorId,
            PreciseTemperatureCelsius,
            Arg.Any<long>());
    }

    [Fact]
    public async Task NotifyReadingRecordedAsync_GivenTimestamp_WhenInvoked_ThenConvertsToUnixTimeSeconds()
    {
        // Given
        var sensorId = SensorId.From(TestSensorId);
        var temperature = Temperature.FromCelsius(StandardTemperatureCelsius);
        var timestamp = DateTimeOffset.FromUnixTimeSeconds(TestUnixTimestamp); // 2024-01-15T10:30:00Z

        // When
        await _sut.NotifyReadingRecordedAsync(sensorId, temperature, timestamp);

        // Then
        await _allClients.Received(1).ReceiveSensorUpdate(
            Arg.Any<string>(),
            Arg.Any<decimal>(),
            TestUnixTimestamp);
    }

    [Theory]
    [InlineData("sensor-a")]
    [InlineData("outdoor-temp")]
    [InlineData("indoor-temp-1")]
    public async Task NotifyReadingRecordedAsync_GivenVariousSensorIds_WhenInvoked_ThenPassesSensorIdCorrectly(string sensorIdValue)
    {
        // Given
        var sensorId = SensorId.From(sensorIdValue);
        var temperature = Temperature.FromCelsius(WarmTemperatureCelsius);
        var timestamp = DateTimeOffset.UtcNow;

        // When
        await _sut.NotifyReadingRecordedAsync(sensorId, temperature, timestamp);

        // Then
        await _allClients.Received(1).ReceiveSensorUpdate(
            sensorIdValue,
            Arg.Any<decimal>(),
            Arg.Any<long>());
    }

    [Fact]
    public async Task NotifyReadingRecordedAsync_GivenCancellationToken_WhenInvoked_ThenCompletesSuccessfully()
    {
        // Given
        var sensorId = SensorId.From(TestSensorId);
        var temperature = Temperature.FromCelsius(StandardTemperatureCelsius);
        var timestamp = DateTimeOffset.UtcNow;
        using var cts = new CancellationTokenSource();

        // When
        await _sut.NotifyReadingRecordedAsync(sensorId, temperature, timestamp, cts.Token);

        // Then
        await _allClients.Received(1).ReceiveSensorUpdate(
            Arg.Any<string>(),
            Arg.Any<decimal>(),
            Arg.Any<long>());
    }

    [Fact]
    public async Task NotifyReadingRecordedAsync_GivenMultipleNotifications_WhenInvoked_ThenEachCallIsForwarded()
    {
        // Given
        var sensorId1 = SensorId.From(Sensor1Id);
        var sensorId2 = SensorId.From(Sensor2Id);
        var temperature = Temperature.FromCelsius(StandardTemperatureCelsius);
        var timestamp = DateTimeOffset.UtcNow;

        // When
        await _sut.NotifyReadingRecordedAsync(sensorId1, temperature, timestamp);
        await _sut.NotifyReadingRecordedAsync(sensorId2, temperature, timestamp);

        // Then
        await _allClients.Received(1).ReceiveSensorUpdate(Sensor1Id, Arg.Any<decimal>(), Arg.Any<long>());
        await _allClients.Received(1).ReceiveSensorUpdate(Sensor2Id, Arg.Any<decimal>(), Arg.Any<long>());
    }

    [Fact]
    public async Task NotifyReadingRecordedAsync_GivenHubThrowsException_WhenInvoked_ThenExceptionPropagates()
    {
        // Given
        var sensorId = SensorId.From(TestSensorId);
        var temperature = Temperature.FromCelsius(StandardTemperatureCelsius);
        var timestamp = DateTimeOffset.UtcNow;
        var expectedException = new InvalidOperationException(HubConnectionFailedMessage);

        _allClients.ReceiveSensorUpdate(Arg.Any<string>(), Arg.Any<decimal>(), Arg.Any<long>())
            .Returns(Task.FromException(expectedException));

        // When
        var act = () => _sut.NotifyReadingRecordedAsync(sensorId, temperature, timestamp);

        // Then
        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage(HubConnectionFailedMessage);
    }

    [Fact]
    public async Task NotifyReadingRecordedAsync_GivenMinimumTemperature_WhenInvoked_ThenHandlesExtremeValue()
    {
        // Given
        var sensorId = SensorId.From(ExtremeSensorId);
        var temperature = Temperature.FromCelsius(AbsoluteZeroCelsius); // Absolute zero
        var timestamp = DateTimeOffset.UtcNow;

        // When
        await _sut.NotifyReadingRecordedAsync(sensorId, temperature, timestamp);

        // Then
        await _allClients.Received(1).ReceiveSensorUpdate(
            ExtremeSensorId,
            AbsoluteZeroCelsius,
            Arg.Any<long>());
    }
}
