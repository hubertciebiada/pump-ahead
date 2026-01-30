using FluentAssertions;
using NSubstitute;
using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.UseCases.Ports.Out;
using PumpAhead.UseCases.Queries.GetTemperatureHistory;

namespace PumpAhead.ProcessModel.Tests.Queries;

public class GetTemperatureHistoryTests
{
    private const string TestSensorId1 = "test-sensor-1";
    private const string TestSensorId2 = "test-sensor-2";
    private const string TestSensorId3 = "test-sensor-3";
    private const string SensorId1Hour = "sensor-1h";
    private const string SensorId1Week = "sensor-1w";
    private const string SensorId1Month = "sensor-1m";
    private const string SensorIdZeroRange = "sensor-zero-range";
    private const string SensorIdLargeDataset = "sensor-large-dataset";
    private const string SensorIdMapping = "sensor-mapping";
    private const string TestSensorId = "test-sensor";
    private const decimal TemperatureCelsius20 = 20m;
    private const decimal TemperatureCelsius21 = 21m;
    private const decimal TemperatureCelsius22 = 22m;
    private const decimal TemperatureCelsius25_5 = 25.5m;
    private const int HoursInDay = 24;
    private const int DaysInWeek = 7;
    private const int LargeDatasetSize = 1000;
    private const int LargeDatasetDays = 30;

    private readonly ITemperatureRepository _repository;
    private readonly GetTemperatureHistory.Handler _handler;

    public GetTemperatureHistoryTests()
    {
        _repository = Substitute.For<ITemperatureRepository>();
        _handler = new GetTemperatureHistory.Handler(_repository);
    }

    [Fact]
    public async Task HandleAsync_WhenNoReadingsExist_ShouldReturnEmptyList()
    {
        // Given
        var sensorId = SensorId.From(TestSensorId1);
        var from = DateTimeOffset.UtcNow.AddHours(-HoursInDay);
        var to = DateTimeOffset.UtcNow;

        _repository
            .GetHistoryAsync(sensorId, from, to, Arg.Any<CancellationToken>())
            .Returns(new List<SensorReading>());

        // When
        var result = await _handler.HandleAsync(new GetTemperatureHistory.Query(sensorId, from, to));

        // Then
        result.Should().NotBeNull();
        result.Readings.Should().BeEmpty();
    }

    [Fact]
    public async Task HandleAsync_WhenReadingsExist_ShouldReturnAllReadings()
    {
        // Given
        var sensorId = SensorId.From(TestSensorId2);
        var from = DateTimeOffset.UtcNow.AddHours(-HoursInDay);
        var to = DateTimeOffset.UtcNow;

        var readings = new List<SensorReading>
        {
            new(sensorId, Temperature.FromCelsius(TemperatureCelsius20), from.AddHours(1)),
            new(sensorId, Temperature.FromCelsius(TemperatureCelsius21), from.AddHours(2)),
            new(sensorId, Temperature.FromCelsius(TemperatureCelsius22), from.AddHours(3))
        };

        _repository
            .GetHistoryAsync(sensorId, from, to, Arg.Any<CancellationToken>())
            .Returns(readings);

        // When
        var result = await _handler.HandleAsync(new GetTemperatureHistory.Query(sensorId, from, to));

        // Then
        result.Readings.Should().HaveCount(3);
        result.Readings[0].Temperature.Celsius.Should().Be(TemperatureCelsius20);
        result.Readings[1].Temperature.Celsius.Should().Be(TemperatureCelsius21);
        result.Readings[2].Temperature.Celsius.Should().Be(TemperatureCelsius22);
    }

    [Fact]
    public async Task HandleAsync_ShouldPreserveTimestamps()
    {
        // Given
        var sensorId = SensorId.From(TestSensorId3);
        var from = DateTimeOffset.UtcNow.AddHours(-HoursInDay);
        var to = DateTimeOffset.UtcNow;
        var timestamp1 = from.AddHours(1);
        var timestamp2 = from.AddHours(2);

        var readings = new List<SensorReading>
        {
            new(sensorId, Temperature.FromCelsius(TemperatureCelsius20), timestamp1),
            new(sensorId, Temperature.FromCelsius(TemperatureCelsius21), timestamp2)
        };

        _repository
            .GetHistoryAsync(sensorId, from, to, Arg.Any<CancellationToken>())
            .Returns(readings);

        // When
        var result = await _handler.HandleAsync(new GetTemperatureHistory.Query(sensorId, from, to));

        // Then
        result.Readings[0].Timestamp.Should().Be(timestamp1);
        result.Readings[1].Timestamp.Should().Be(timestamp2);
    }

    [Fact]
    public async Task HandleAsync_WithOneHourRange_ShouldQueryCorrectTimeRange()
    {
        // Given
        var sensorId = SensorId.From(SensorId1Hour);
        var to = DateTimeOffset.UtcNow;
        var from = to.AddHours(-1);

        _repository
            .GetHistoryAsync(sensorId, from, to, Arg.Any<CancellationToken>())
            .Returns(new List<SensorReading>());

        // When
        await _handler.HandleAsync(new GetTemperatureHistory.Query(sensorId, from, to));

        // Then
        await _repository.Received(1).GetHistoryAsync(sensorId, from, to, Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task HandleAsync_WithOneWeekRange_ShouldQueryCorrectTimeRange()
    {
        // Given
        var sensorId = SensorId.From(SensorId1Week);
        var to = DateTimeOffset.UtcNow;
        var from = to.AddDays(-DaysInWeek);

        _repository
            .GetHistoryAsync(sensorId, from, to, Arg.Any<CancellationToken>())
            .Returns(new List<SensorReading>());

        // When
        await _handler.HandleAsync(new GetTemperatureHistory.Query(sensorId, from, to));

        // Then
        await _repository.Received(1).GetHistoryAsync(sensorId, from, to, Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task HandleAsync_WithOneMonthRange_ShouldQueryCorrectTimeRange()
    {
        // Given
        var sensorId = SensorId.From(SensorId1Month);
        var to = DateTimeOffset.UtcNow;
        var from = to.AddMonths(-1);

        _repository
            .GetHistoryAsync(sensorId, from, to, Arg.Any<CancellationToken>())
            .Returns(new List<SensorReading>());

        // When
        await _handler.HandleAsync(new GetTemperatureHistory.Query(sensorId, from, to));

        // Then
        await _repository.Received(1).GetHistoryAsync(sensorId, from, to, Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task HandleAsync_WithZeroRange_ShouldStillReturnResult()
    {
        // Given
        var sensorId = SensorId.From(SensorIdZeroRange);
        var timestamp = DateTimeOffset.UtcNow;

        _repository
            .GetHistoryAsync(sensorId, timestamp, timestamp, Arg.Any<CancellationToken>())
            .Returns(new List<SensorReading>());

        // When
        var result = await _handler.HandleAsync(new GetTemperatureHistory.Query(sensorId, timestamp, timestamp));

        // Then
        result.Should().NotBeNull();
        result.Readings.Should().BeEmpty();
    }

    [Fact]
    public async Task HandleAsync_WithLargeDataset_ShouldReturnAllReadings()
    {
        // Given
        var sensorId = SensorId.From(SensorIdLargeDataset);
        var from = DateTimeOffset.UtcNow.AddDays(-LargeDatasetDays);
        var to = DateTimeOffset.UtcNow;

        var readings = Enumerable.Range(0, LargeDatasetSize)
            .Select(i => new SensorReading(
                sensorId,
                Temperature.FromCelsius(20m + i * 0.01m),
                from.AddMinutes(i * 43)))
            .ToList();

        _repository
            .GetHistoryAsync(sensorId, from, to, Arg.Any<CancellationToken>())
            .Returns(readings);

        // When
        var result = await _handler.HandleAsync(new GetTemperatureHistory.Query(sensorId, from, to));

        // Then
        result.Readings.Should().HaveCount(LargeDatasetSize);
    }

    [Fact]
    public async Task HandleAsync_ShouldMapReadingsToDataPoints()
    {
        // Given
        var sensorId = SensorId.From(SensorIdMapping);
        var from = DateTimeOffset.UtcNow.AddHours(-1);
        var to = DateTimeOffset.UtcNow;
        var temperature = Temperature.FromCelsius(TemperatureCelsius25_5);
        var timestamp = from.AddMinutes(30);

        var readings = new List<SensorReading>
        {
            new(sensorId, temperature, timestamp)
        };

        _repository
            .GetHistoryAsync(sensorId, from, to, Arg.Any<CancellationToken>())
            .Returns(readings);

        // When
        var result = await _handler.HandleAsync(new GetTemperatureHistory.Query(sensorId, from, to));

        // Then
        result.Readings.Should().ContainSingle();
        var dataPoint = result.Readings[0];
        dataPoint.Temperature.Should().Be(temperature);
        dataPoint.Timestamp.Should().Be(timestamp);
    }

    [Fact]
    public async Task HandleAsync_ShouldPassCancellationToken()
    {
        // Given
        var sensorId = SensorId.From(TestSensorId);
        var from = DateTimeOffset.UtcNow.AddHours(-1);
        var to = DateTimeOffset.UtcNow;
        var cancellationToken = new CancellationToken();

        _repository
            .GetHistoryAsync(sensorId, from, to, cancellationToken)
            .Returns(new List<SensorReading>());

        // When
        await _handler.HandleAsync(new GetTemperatureHistory.Query(sensorId, from, to), cancellationToken);

        // Then
        await _repository.Received(1).GetHistoryAsync(sensorId, from, to, cancellationToken);
    }
}
