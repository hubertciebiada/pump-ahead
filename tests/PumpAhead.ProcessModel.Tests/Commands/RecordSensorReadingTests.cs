using FluentAssertions;
using NSubstitute;
using NSubstitute.ExceptionExtensions;
using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.UseCases.Commands.RecordSensorReading;
using PumpAhead.UseCases.Ports.Out;

namespace PumpAhead.ProcessModel.Tests.Commands;

public class RecordSensorReadingTests
{
    private const string ExistingSensorId = "existing-sensor";
    private const string TestSensorId = "test-sensor";
    private const string NonExistentSensorId = "non-existent-sensor";
    private const string SensorWithOldLastSeenId = "sensor-with-old-lastseen";
    private const string NeverSeenSensorId = "never-seen-sensor";
    private const string MultiReadingSensorId = "multi-reading-sensor";
    private const string FreezerSensorId = "freezer-sensor";
    private const string ZeroTempSensorId = "zero-temp-sensor";
    private const string DefaultAddress = "192.168.1.100";
    private const string DefaultSensorType = "DS18B20";
    private const string DatabaseErrorMessage = "Database error";
    private const string SensorRepositoryErrorMessage = "Sensor repository error";
    private const string NotificationErrorMessage = "Notification error";
    private const decimal DefaultTemperatureCelsius = 22.5m;
    private const decimal RoomTemperatureCelsius = 20.0m;
    private const decimal SlightlyHigherTemperatureCelsius = 21.0m;
    private const decimal WarmTemperatureCelsius = 25.0m;
    private const decimal MildTemperatureCelsius = 23.0m;
    private const decimal NegativeTemperatureCelsius = -18.5m;
    private const decimal ZeroTemperatureCelsius = 0m;
    private const int MultipleReadingsDelayMinutes = 5;

    private readonly ISensorRepository _sensorRepository;
    private readonly ITemperatureRepository _temperatureRepository;
    private readonly ISensorNotificationService _notificationService;
    private readonly RecordSensorReading.Handler _handler;

    public RecordSensorReadingTests()
    {
        _sensorRepository = Substitute.For<ISensorRepository>();
        _temperatureRepository = Substitute.For<ITemperatureRepository>();
        _notificationService = Substitute.For<ISensorNotificationService>();
        _handler = new RecordSensorReading.Handler(
            _sensorRepository,
            _temperatureRepository,
            _notificationService);
    }

    #region Saving Sensor Reading

    [Fact]
    public async Task HandleAsync_WhenSensorExists_ShouldSaveTemperatureReading()
    {
        // Given
        var sensorId = SensorId.From(ExistingSensorId);
        var temperature = Temperature.FromCelsius(DefaultTemperatureCelsius);
        var timestamp = DateTimeOffset.UtcNow;
        var command = new RecordSensorReading.Command(sensorId, temperature, timestamp);

        var existingSensor = CreateSensorInfo(sensorId);
        _sensorRepository.GetByIdAsync(sensorId, Arg.Any<CancellationToken>())
            .Returns(existingSensor);

        // When
        await _handler.HandleAsync(command);

        // Then
        await _temperatureRepository.Received(1).SaveAsync(
            Arg.Is<SensorReading>(r =>
                r.SensorId == sensorId &&
                r.Temperature == temperature &&
                r.Timestamp == timestamp),
            Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task HandleAsync_WhenSensorExists_ShouldUpdateLastSeen()
    {
        // Given
        var sensorId = SensorId.From(ExistingSensorId);
        var temperature = Temperature.FromCelsius(DefaultTemperatureCelsius);
        var timestamp = DateTimeOffset.UtcNow;
        var command = new RecordSensorReading.Command(sensorId, temperature, timestamp);

        var existingSensor = CreateSensorInfo(sensorId);
        _sensorRepository.GetByIdAsync(sensorId, Arg.Any<CancellationToken>())
            .Returns(existingSensor);

        // When
        await _handler.HandleAsync(command);

        // Then
        await _sensorRepository.Received(1).UpdateLastSeenAsync(
            sensorId,
            timestamp,
            Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task HandleAsync_WhenSensorExists_ShouldNotifyReadingRecorded()
    {
        // Given
        var sensorId = SensorId.From(ExistingSensorId);
        var temperature = Temperature.FromCelsius(DefaultTemperatureCelsius);
        var timestamp = DateTimeOffset.UtcNow;
        var command = new RecordSensorReading.Command(sensorId, temperature, timestamp);

        var existingSensor = CreateSensorInfo(sensorId);
        _sensorRepository.GetByIdAsync(sensorId, Arg.Any<CancellationToken>())
            .Returns(existingSensor);

        // When
        await _handler.HandleAsync(command);

        // Then
        await _notificationService.Received(1).NotifyReadingRecordedAsync(
            sensorId,
            temperature,
            timestamp,
            Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task HandleAsync_ShouldPassCancellationToken()
    {
        // Given
        var sensorId = SensorId.From(TestSensorId);
        var temperature = Temperature.FromCelsius(RoomTemperatureCelsius);
        var timestamp = DateTimeOffset.UtcNow;
        var command = new RecordSensorReading.Command(sensorId, temperature, timestamp);
        using var cts = new CancellationTokenSource();
        var cancellationToken = cts.Token;

        var existingSensor = CreateSensorInfo(sensorId);
        _sensorRepository.GetByIdAsync(sensorId, cancellationToken)
            .Returns(existingSensor);

        // When
        await _handler.HandleAsync(command, cancellationToken);

        // Then
        await _sensorRepository.Received(1).GetByIdAsync(sensorId, cancellationToken);
        await _sensorRepository.Received(1).UpdateLastSeenAsync(sensorId, timestamp, cancellationToken);
        await _temperatureRepository.Received(1).SaveAsync(Arg.Any<SensorReading>(), cancellationToken);
        await _notificationService.Received(1).NotifyReadingRecordedAsync(
            sensorId, temperature, timestamp, cancellationToken);
    }

    #endregion

    #region Sensor Does Not Exist

    [Fact]
    public async Task HandleAsync_WhenSensorDoesNotExist_ShouldThrowInvalidOperationException()
    {
        // Given
        var sensorId = SensorId.From(NonExistentSensorId);
        var temperature = Temperature.FromCelsius(DefaultTemperatureCelsius);
        var timestamp = DateTimeOffset.UtcNow;
        var command = new RecordSensorReading.Command(sensorId, temperature, timestamp);

        _sensorRepository.GetByIdAsync(sensorId, Arg.Any<CancellationToken>())
            .Returns((SensorInfo?)null);

        // When
        var act = () => _handler.HandleAsync(command);

        // Then
        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage($"Sensor '{sensorId.Value}' does not exist. Register the sensor first.");
    }

    [Fact]
    public async Task HandleAsync_WhenSensorDoesNotExist_ShouldNotSaveReading()
    {
        // Given
        var sensorId = SensorId.From(NonExistentSensorId);
        var command = new RecordSensorReading.Command(
            sensorId,
            Temperature.FromCelsius(DefaultTemperatureCelsius),
            DateTimeOffset.UtcNow);

        _sensorRepository.GetByIdAsync(sensorId, Arg.Any<CancellationToken>())
            .Returns((SensorInfo?)null);

        // When
        var act = () => _handler.HandleAsync(command);

        // Then
        await act.Should().ThrowAsync<InvalidOperationException>();
        await _temperatureRepository.DidNotReceive().SaveAsync(
            Arg.Any<SensorReading>(),
            Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task HandleAsync_WhenSensorDoesNotExist_ShouldNotUpdateLastSeen()
    {
        // Given
        var sensorId = SensorId.From(NonExistentSensorId);
        var command = new RecordSensorReading.Command(
            sensorId,
            Temperature.FromCelsius(DefaultTemperatureCelsius),
            DateTimeOffset.UtcNow);

        _sensorRepository.GetByIdAsync(sensorId, Arg.Any<CancellationToken>())
            .Returns((SensorInfo?)null);

        // When
        var act = () => _handler.HandleAsync(command);

        // Then
        await act.Should().ThrowAsync<InvalidOperationException>();
        await _sensorRepository.DidNotReceive().UpdateLastSeenAsync(
            Arg.Any<SensorId>(),
            Arg.Any<DateTimeOffset>(),
            Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task HandleAsync_WhenSensorDoesNotExist_ShouldNotNotify()
    {
        // Given
        var sensorId = SensorId.From(NonExistentSensorId);
        var command = new RecordSensorReading.Command(
            sensorId,
            Temperature.FromCelsius(DefaultTemperatureCelsius),
            DateTimeOffset.UtcNow);

        _sensorRepository.GetByIdAsync(sensorId, Arg.Any<CancellationToken>())
            .Returns((SensorInfo?)null);

        // When
        var act = () => _handler.HandleAsync(command);

        // Then
        await act.Should().ThrowAsync<InvalidOperationException>();
        await _notificationService.DidNotReceive().NotifyReadingRecordedAsync(
            Arg.Any<SensorId>(),
            Arg.Any<Temperature>(),
            Arg.Any<DateTimeOffset>(),
            Arg.Any<CancellationToken>());
    }

    #endregion

    #region Updating Existing Sensor

    [Fact]
    public async Task HandleAsync_WhenExistingSensorWithOldLastSeen_ShouldUpdateToNewTimestamp()
    {
        // Given
        var sensorId = SensorId.From(SensorWithOldLastSeenId);
        var oldLastSeen = DateTimeOffset.UtcNow.AddDays(-1);
        var newTimestamp = DateTimeOffset.UtcNow;
        var temperature = Temperature.FromCelsius(WarmTemperatureCelsius);
        var command = new RecordSensorReading.Command(sensorId, temperature, newTimestamp);

        var existingSensor = CreateSensorInfo(sensorId, lastSeenAt: oldLastSeen);
        _sensorRepository.GetByIdAsync(sensorId, Arg.Any<CancellationToken>())
            .Returns(existingSensor);

        // When
        await _handler.HandleAsync(command);

        // Then
        await _sensorRepository.Received(1).UpdateLastSeenAsync(
            sensorId,
            newTimestamp,
            Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task HandleAsync_WhenExistingSensorNeverSeen_ShouldSetLastSeen()
    {
        // Given
        var sensorId = SensorId.From(NeverSeenSensorId);
        var timestamp = DateTimeOffset.UtcNow;
        var temperature = Temperature.FromCelsius(MildTemperatureCelsius);
        var command = new RecordSensorReading.Command(sensorId, temperature, timestamp);

        var existingSensor = CreateSensorInfo(sensorId, lastSeenAt: null);
        _sensorRepository.GetByIdAsync(sensorId, Arg.Any<CancellationToken>())
            .Returns(existingSensor);

        // When
        await _handler.HandleAsync(command);

        // Then
        await _sensorRepository.Received(1).UpdateLastSeenAsync(
            sensorId,
            timestamp,
            Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task HandleAsync_WhenMultipleReadingsForSameSensor_ShouldUpdateLastSeenEachTime()
    {
        // Given
        var sensorId = SensorId.From(MultiReadingSensorId);
        var timestamp1 = DateTimeOffset.UtcNow;
        var timestamp2 = timestamp1.AddMinutes(MultipleReadingsDelayMinutes);
        var command1 = new RecordSensorReading.Command(sensorId, Temperature.FromCelsius(RoomTemperatureCelsius), timestamp1);
        var command2 = new RecordSensorReading.Command(sensorId, Temperature.FromCelsius(SlightlyHigherTemperatureCelsius), timestamp2);

        var existingSensor = CreateSensorInfo(sensorId);
        _sensorRepository.GetByIdAsync(sensorId, Arg.Any<CancellationToken>())
            .Returns(existingSensor);

        // When
        await _handler.HandleAsync(command1);
        await _handler.HandleAsync(command2);

        // Then
        await _sensorRepository.Received(1).UpdateLastSeenAsync(sensorId, timestamp1, Arg.Any<CancellationToken>());
        await _sensorRepository.Received(1).UpdateLastSeenAsync(sensorId, timestamp2, Arg.Any<CancellationToken>());
    }

    #endregion

    #region Edge Cases

    [Fact]
    public async Task HandleAsync_WhenNegativeTemperature_ShouldSaveCorrectly()
    {
        // Given
        var sensorId = SensorId.From(FreezerSensorId);
        var temperature = Temperature.FromCelsius(NegativeTemperatureCelsius);
        var timestamp = DateTimeOffset.UtcNow;
        var command = new RecordSensorReading.Command(sensorId, temperature, timestamp);

        var existingSensor = CreateSensorInfo(sensorId);
        _sensorRepository.GetByIdAsync(sensorId, Arg.Any<CancellationToken>())
            .Returns(existingSensor);

        // When
        await _handler.HandleAsync(command);

        // Then
        await _temperatureRepository.Received(1).SaveAsync(
            Arg.Is<SensorReading>(r => r.Temperature.Celsius == NegativeTemperatureCelsius),
            Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task HandleAsync_WhenZeroTemperature_ShouldSaveCorrectly()
    {
        // Given
        var sensorId = SensorId.From(ZeroTempSensorId);
        var temperature = Temperature.FromCelsius(ZeroTemperatureCelsius);
        var timestamp = DateTimeOffset.UtcNow;
        var command = new RecordSensorReading.Command(sensorId, temperature, timestamp);

        var existingSensor = CreateSensorInfo(sensorId);
        _sensorRepository.GetByIdAsync(sensorId, Arg.Any<CancellationToken>())
            .Returns(existingSensor);

        // When
        await _handler.HandleAsync(command);

        // Then
        await _temperatureRepository.Received(1).SaveAsync(
            Arg.Is<SensorReading>(r => r.Temperature.Celsius == ZeroTemperatureCelsius),
            Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task HandleAsync_WhenTemperatureRepositoryThrows_ShouldPropagateException()
    {
        // Given
        var sensorId = SensorId.From(TestSensorId);
        var command = new RecordSensorReading.Command(
            sensorId,
            Temperature.FromCelsius(DefaultTemperatureCelsius),
            DateTimeOffset.UtcNow);

        var existingSensor = CreateSensorInfo(sensorId);
        _sensorRepository.GetByIdAsync(sensorId, Arg.Any<CancellationToken>())
            .Returns(existingSensor);
        _temperatureRepository
            .SaveAsync(Arg.Any<SensorReading>(), Arg.Any<CancellationToken>())
            .ThrowsAsync(new InvalidOperationException(DatabaseErrorMessage));

        // When
        var act = () => _handler.HandleAsync(command);

        // Then
        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage(DatabaseErrorMessage);
    }

    [Fact]
    public async Task HandleAsync_WhenSensorRepositoryThrows_ShouldPropagateException()
    {
        // Given
        var sensorId = SensorId.From(TestSensorId);
        var command = new RecordSensorReading.Command(
            sensorId,
            Temperature.FromCelsius(DefaultTemperatureCelsius),
            DateTimeOffset.UtcNow);

        _sensorRepository
            .GetByIdAsync(sensorId, Arg.Any<CancellationToken>())
            .ThrowsAsync(new InvalidOperationException(SensorRepositoryErrorMessage));

        // When
        var act = () => _handler.HandleAsync(command);

        // Then
        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage(SensorRepositoryErrorMessage);
    }

    [Fact]
    public async Task HandleAsync_WhenNotificationServiceThrows_ShouldPropagateException()
    {
        // Given
        var sensorId = SensorId.From(TestSensorId);
        var command = new RecordSensorReading.Command(
            sensorId,
            Temperature.FromCelsius(DefaultTemperatureCelsius),
            DateTimeOffset.UtcNow);

        var existingSensor = CreateSensorInfo(sensorId);
        _sensorRepository.GetByIdAsync(sensorId, Arg.Any<CancellationToken>())
            .Returns(existingSensor);
        _notificationService
            .NotifyReadingRecordedAsync(
                Arg.Any<SensorId>(),
                Arg.Any<Temperature>(),
                Arg.Any<DateTimeOffset>(),
                Arg.Any<CancellationToken>())
            .ThrowsAsync(new InvalidOperationException(NotificationErrorMessage));

        // When
        var act = () => _handler.HandleAsync(command);

        // Then
        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage(NotificationErrorMessage);
    }

    #endregion

    #region Helper Methods

    private static SensorInfo CreateSensorInfo(
        SensorId sensorId,
        string? name = null,
        string? label = null,
        string? address = null,
        string? type = null,
        bool isActive = true,
        DateTimeOffset? lastSeenAt = null)
    {
        return new SensorInfo(
            Id: sensorId,
            Name: name ?? $"Sensor {sensorId.Value}",
            Label: label,
            Address: address ?? DefaultAddress,
            Type: type ?? DefaultSensorType,
            IsActive: isActive,
            LastSeenAt: lastSeenAt);
    }

    #endregion
}
