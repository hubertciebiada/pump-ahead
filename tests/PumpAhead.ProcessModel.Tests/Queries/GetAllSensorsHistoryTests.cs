using FluentAssertions;
using NSubstitute;
using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.UseCases.Ports.Out;
using PumpAhead.UseCases.Queries.GetAllSensorsHistory;

namespace PumpAhead.ProcessModel.Tests.Queries;

public class GetAllSensorsHistoryTests
{
    private const string SensorId1 = "sensor-1";
    private const string SensorId2 = "sensor-2";
    private const string SensorId3 = "sensor-3";
    private const string SensorIdNoReadings = "sensor-no-readings";
    private const string SensorIdWithLabel = "sensor-with-label";
    private const string SensorIdAsDisplay = "sensor-id-as-display";
    private const string SensorIdMapping = "sensor-mapping";
    private const string SensorIdWithData = "sensor-with-data";
    private const string SensorIdWithoutData = "sensor-without-data";
    private const string SensorIdWithLotsOfData = "sensor-with-lots-of-data";
    private const string DefaultSensorType = "DefaultSensorType";
    private const string SensorName1 = "Sensor 1";
    private const string SensorName2 = "Sensor 2";
    private const string SensorName3 = "Sensor 3";
    private const string LivingRoomLabel = "Living Room";
    private const string BedroomLabel = "Bedroom";
    private const string CustomLabel = "Custom Label";
    private const string Label1 = "Label 1";
    private const string Label2 = "Label 2";
    private const string Label3 = "Label 3";
    private const int HoursInDay = 24;
    private const int DaysInWeek = 7;
    private const int LargeDatasetReadings = 100;
    private const decimal TemperatureCelsius20 = 20m;
    private const decimal TemperatureCelsius21 = 21m;
    private const decimal TemperatureCelsius22 = 22m;
    private const decimal TemperatureCelsius23 = 23m;
    private const decimal TemperatureCelsius24 = 24m;
    private const decimal TemperatureCelsius25 = 25m;
    private const decimal TemperatureCelsius25_5 = 25.5m;
    private const decimal TemperatureCelsius15 = 15m;

    private readonly ISensorRepository _sensorRepository;
    private readonly ITemperatureRepository _temperatureRepository;
    private readonly GetAllSensorsHistory.Handler _handler;

    public GetAllSensorsHistoryTests()
    {
        _sensorRepository = Substitute.For<ISensorRepository>();
        _temperatureRepository = Substitute.For<ITemperatureRepository>();
        _handler = new GetAllSensorsHistory.Handler(_sensorRepository, _temperatureRepository);
    }

    [Fact]
    public async Task HandleAsync_WhenNoSensorsExist_ShouldReturnEmptyList()
    {
        // Given
        var from = DateTimeOffset.UtcNow.AddHours(-HoursInDay);
        var to = DateTimeOffset.UtcNow;

        _sensorRepository
            .GetAllActiveAsync(Arg.Any<CancellationToken>())
            .Returns(new List<SensorInfo>());

        _temperatureRepository
            .GetHistoryBatchAsync(
                Arg.Any<IReadOnlyList<SensorId>>(),
                from,
                to,
                Arg.Any<CancellationToken>())
            .Returns(new Dictionary<SensorId, IReadOnlyList<SensorReading>>());

        // When
        var result = await _handler.HandleAsync(new GetAllSensorsHistory.Query(from, to));

        // Then
        result.Should().NotBeNull();
        result.Sensors.Should().BeEmpty();
    }

    [Fact]
    public async Task HandleAsync_WhenSensorsExist_ShouldReturnAllSensorData()
    {
        // Given
        var from = DateTimeOffset.UtcNow.AddHours(-HoursInDay);
        var to = DateTimeOffset.UtcNow;

        var sensor1Id = SensorId.From(SensorId1);
        var sensor2Id = SensorId.From(SensorId2);

        var sensors = new List<SensorInfo>
        {
            new(sensor1Id, SensorName1, LivingRoomLabel, "address1", "DefaultSensorType", true, DateTimeOffset.UtcNow),
            new(sensor2Id, SensorName2, BedroomLabel, "address2", "DefaultSensorType", true, DateTimeOffset.UtcNow)
        };

        _sensorRepository
            .GetAllActiveAsync(Arg.Any<CancellationToken>())
            .Returns(sensors);

        var readings = new Dictionary<SensorId, IReadOnlyList<SensorReading>>
        {
            [sensor1Id] = new List<SensorReading>
            {
                new(sensor1Id, Temperature.FromCelsius(TemperatureCelsius21), from.AddHours(1))
            },
            [sensor2Id] = new List<SensorReading>
            {
                new(sensor2Id, Temperature.FromCelsius(TemperatureCelsius22), from.AddHours(1))
            }
        };

        _temperatureRepository
            .GetHistoryBatchAsync(
                Arg.Any<IReadOnlyList<SensorId>>(),
                from,
                to,
                Arg.Any<CancellationToken>())
            .Returns(readings);

        // When
        var result = await _handler.HandleAsync(new GetAllSensorsHistory.Query(from, to));

        // Then
        result.Sensors.Should().HaveCount(2);
        result.Sensors.Should().Contain(s => s.SensorId == sensor1Id);
        result.Sensors.Should().Contain(s => s.SensorId == sensor2Id);
    }

    [Fact]
    public async Task HandleAsync_ShouldAggregateDataFromAllSensors()
    {
        // Given
        var from = DateTimeOffset.UtcNow.AddHours(-HoursInDay);
        var to = DateTimeOffset.UtcNow;

        var sensor1Id = SensorId.From(SensorId1);
        var sensor2Id = SensorId.From(SensorId2);
        var sensor3Id = SensorId.From(SensorId3);

        var sensors = new List<SensorInfo>
        {
            new(sensor1Id, SensorName1, Label1, "address1", "DefaultSensorType", true, null),
            new(sensor2Id, SensorName2, Label2, "address2", "DefaultSensorType", true, null),
            new(sensor3Id, SensorName3, Label3, "address3", "DefaultSensorType", true, null)
        };

        _sensorRepository
            .GetAllActiveAsync(Arg.Any<CancellationToken>())
            .Returns(sensors);

        var readings = new Dictionary<SensorId, IReadOnlyList<SensorReading>>
        {
            [sensor1Id] = new List<SensorReading>
            {
                new(sensor1Id, Temperature.FromCelsius(TemperatureCelsius20), from.AddHours(1)),
                new(sensor1Id, Temperature.FromCelsius(TemperatureCelsius21), from.AddHours(2))
            },
            [sensor2Id] = new List<SensorReading>
            {
                new(sensor2Id, Temperature.FromCelsius(TemperatureCelsius22), from.AddHours(1))
            },
            [sensor3Id] = new List<SensorReading>
            {
                new(sensor3Id, Temperature.FromCelsius(TemperatureCelsius23), from.AddHours(1)),
                new(sensor3Id, Temperature.FromCelsius(TemperatureCelsius24), from.AddHours(2)),
                new(sensor3Id, Temperature.FromCelsius(TemperatureCelsius25), from.AddHours(3))
            }
        };

        _temperatureRepository
            .GetHistoryBatchAsync(
                Arg.Any<IReadOnlyList<SensorId>>(),
                from,
                to,
                Arg.Any<CancellationToken>())
            .Returns(readings);

        // When
        var result = await _handler.HandleAsync(new GetAllSensorsHistory.Query(from, to));

        // Then
        result.Sensors.Should().HaveCount(3);

        var sensor1Data = result.Sensors.First(s => s.SensorId == sensor1Id);
        sensor1Data.Readings.Should().HaveCount(2);

        var sensor2Data = result.Sensors.First(s => s.SensorId == sensor2Id);
        sensor2Data.Readings.Should().HaveCount(1);

        var sensor3Data = result.Sensors.First(s => s.SensorId == sensor3Id);
        sensor3Data.Readings.Should().HaveCount(3);
    }

    [Fact]
    public async Task HandleAsync_WhenSensorHasNoReadings_ShouldReturnEmptyReadingsList()
    {
        // Given
        var from = DateTimeOffset.UtcNow.AddHours(-HoursInDay);
        var to = DateTimeOffset.UtcNow;

        var sensorId = SensorId.From(SensorIdNoReadings);

        var sensors = new List<SensorInfo>
        {
            new(sensorId, "Sensor", "Label", "address", "DefaultSensorType", true, null)
        };

        _sensorRepository
            .GetAllActiveAsync(Arg.Any<CancellationToken>())
            .Returns(sensors);

        _temperatureRepository
            .GetHistoryBatchAsync(
                Arg.Any<IReadOnlyList<SensorId>>(),
                from,
                to,
                Arg.Any<CancellationToken>())
            .Returns(new Dictionary<SensorId, IReadOnlyList<SensorReading>>());

        // When
        var result = await _handler.HandleAsync(new GetAllSensorsHistory.Query(from, to));

        // Then
        result.Sensors.Should().ContainSingle();
        result.Sensors[0].Readings.Should().BeEmpty();
    }

    [Fact]
    public async Task HandleAsync_ShouldIncludeDisplayNameFromSensor()
    {
        // Given
        var from = DateTimeOffset.UtcNow.AddHours(-HoursInDay);
        var to = DateTimeOffset.UtcNow;

        var sensorId = SensorId.From(SensorIdWithLabel);

        var sensors = new List<SensorInfo>
        {
            new(sensorId, "Sensor Name", CustomLabel, "address", "DefaultSensorType", true, null)
        };

        _sensorRepository
            .GetAllActiveAsync(Arg.Any<CancellationToken>())
            .Returns(sensors);

        _temperatureRepository
            .GetHistoryBatchAsync(
                Arg.Any<IReadOnlyList<SensorId>>(),
                from,
                to,
                Arg.Any<CancellationToken>())
            .Returns(new Dictionary<SensorId, IReadOnlyList<SensorReading>>());

        // When
        var result = await _handler.HandleAsync(new GetAllSensorsHistory.Query(from, to));

        // Then
        result.Sensors.Should().ContainSingle();
        result.Sensors[0].DisplayName.Should().Be(CustomLabel);
    }

    [Fact]
    public async Task HandleAsync_WhenLabelIsEmpty_ShouldUseSensorIdAsDisplayName()
    {
        // Given
        var from = DateTimeOffset.UtcNow.AddHours(-HoursInDay);
        var to = DateTimeOffset.UtcNow;

        var sensorId = SensorId.From(SensorIdAsDisplay);

        var sensors = new List<SensorInfo>
        {
            new(sensorId, "Sensor Name", null, "address", "DefaultSensorType", true, null)
        };

        _sensorRepository
            .GetAllActiveAsync(Arg.Any<CancellationToken>())
            .Returns(sensors);

        _temperatureRepository
            .GetHistoryBatchAsync(
                Arg.Any<IReadOnlyList<SensorId>>(),
                from,
                to,
                Arg.Any<CancellationToken>())
            .Returns(new Dictionary<SensorId, IReadOnlyList<SensorReading>>());

        // When
        var result = await _handler.HandleAsync(new GetAllSensorsHistory.Query(from, to));

        // Then
        result.Sensors.Should().ContainSingle();
        result.Sensors[0].DisplayName.Should().Be(SensorIdAsDisplay);
    }

    [Fact]
    public async Task HandleAsync_ShouldCallRepositoriesWithCorrectParameters()
    {
        // Given
        var from = DateTimeOffset.UtcNow.AddHours(-HoursInDay);
        var to = DateTimeOffset.UtcNow;

        var sensorId = SensorId.From(SensorId1);

        var sensors = new List<SensorInfo>
        {
            new(sensorId, "Sensor", "Label", "address", "DefaultSensorType", true, null)
        };

        _sensorRepository
            .GetAllActiveAsync(Arg.Any<CancellationToken>())
            .Returns(sensors);

        _temperatureRepository
            .GetHistoryBatchAsync(
                Arg.Any<IReadOnlyList<SensorId>>(),
                from,
                to,
                Arg.Any<CancellationToken>())
            .Returns(new Dictionary<SensorId, IReadOnlyList<SensorReading>>());

        // When
        await _handler.HandleAsync(new GetAllSensorsHistory.Query(from, to));

        // Then
        await _sensorRepository.Received(1).GetAllActiveAsync(Arg.Any<CancellationToken>());
        await _temperatureRepository.Received(1).GetHistoryBatchAsync(
            Arg.Is<IReadOnlyList<SensorId>>(ids => ids.Contains(sensorId)),
            from,
            to,
            Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task HandleAsync_ShouldPassCancellationToken()
    {
        // Given
        var from = DateTimeOffset.UtcNow.AddHours(-1);
        var to = DateTimeOffset.UtcNow;
        var cancellationToken = new CancellationToken();

        _sensorRepository
            .GetAllActiveAsync(cancellationToken)
            .Returns(new List<SensorInfo>());

        _temperatureRepository
            .GetHistoryBatchAsync(
                Arg.Any<IReadOnlyList<SensorId>>(),
                from,
                to,
                cancellationToken)
            .Returns(new Dictionary<SensorId, IReadOnlyList<SensorReading>>());

        // When
        await _handler.HandleAsync(new GetAllSensorsHistory.Query(from, to), cancellationToken);

        // Then
        await _sensorRepository.Received(1).GetAllActiveAsync(cancellationToken);
        await _temperatureRepository.Received(1).GetHistoryBatchAsync(
            Arg.Any<IReadOnlyList<SensorId>>(),
            from,
            to,
            cancellationToken);
    }

    [Fact]
    public async Task HandleAsync_ShouldMapReadingsToDataPointsCorrectly()
    {
        // Given
        var from = DateTimeOffset.UtcNow.AddHours(-HoursInDay);
        var to = DateTimeOffset.UtcNow;

        var sensorId = SensorId.From(SensorIdMapping);
        var temperature = Temperature.FromCelsius(TemperatureCelsius25_5);
        var timestamp = from.AddHours(12);

        var sensors = new List<SensorInfo>
        {
            new(sensorId, "Sensor", "Label", "address", "DefaultSensorType", true, null)
        };

        _sensorRepository
            .GetAllActiveAsync(Arg.Any<CancellationToken>())
            .Returns(sensors);

        var readings = new Dictionary<SensorId, IReadOnlyList<SensorReading>>
        {
            [sensorId] = new List<SensorReading>
            {
                new(sensorId, temperature, timestamp)
            }
        };

        _temperatureRepository
            .GetHistoryBatchAsync(
                Arg.Any<IReadOnlyList<SensorId>>(),
                from,
                to,
                Arg.Any<CancellationToken>())
            .Returns(readings);

        // When
        var result = await _handler.HandleAsync(new GetAllSensorsHistory.Query(from, to));

        // Then
        result.Sensors.Should().ContainSingle();
        var sensorData = result.Sensors[0];
        sensorData.Readings.Should().ContainSingle();
        sensorData.Readings[0].Temperature.Should().Be(temperature);
        sensorData.Readings[0].Timestamp.Should().Be(timestamp);
    }

    [Fact]
    public async Task HandleAsync_WithMultipleSensorsAndMixedData_ShouldAggregateCorrectly()
    {
        // Given
        var from = DateTimeOffset.UtcNow.AddDays(-DaysInWeek);
        var to = DateTimeOffset.UtcNow;

        var sensor1Id = SensorId.From(SensorIdWithData);
        var sensor2Id = SensorId.From(SensorIdWithoutData);
        var sensor3Id = SensorId.From(SensorIdWithLotsOfData);

        var sensors = new List<SensorInfo>
        {
            new(sensor1Id, SensorName1, Label1, "address1", "DefaultSensorType", true, null),
            new(sensor2Id, SensorName2, Label2, "address2", "DefaultSensorType", true, null),
            new(sensor3Id, SensorName3, Label3, "address3", "DefaultSensorType", true, null)
        };

        _sensorRepository
            .GetAllActiveAsync(Arg.Any<CancellationToken>())
            .Returns(sensors);

        var readings = new Dictionary<SensorId, IReadOnlyList<SensorReading>>
        {
            [sensor1Id] = new List<SensorReading>
            {
                new(sensor1Id, Temperature.FromCelsius(TemperatureCelsius20), from.AddHours(1))
            },
            // sensor2Id intentionally missing - no data
            [sensor3Id] = Enumerable.Range(0, LargeDatasetReadings)
                .Select(i => new SensorReading(
                    sensor3Id,
                    Temperature.FromCelsius(TemperatureCelsius15 + i * 0.1m),
                    from.AddHours(i)))
                .ToList()
        };

        _temperatureRepository
            .GetHistoryBatchAsync(
                Arg.Any<IReadOnlyList<SensorId>>(),
                from,
                to,
                Arg.Any<CancellationToken>())
            .Returns(readings);

        // When
        var result = await _handler.HandleAsync(new GetAllSensorsHistory.Query(from, to));

        // Then
        result.Sensors.Should().HaveCount(3);

        var sensor1Data = result.Sensors.First(s => s.SensorId == sensor1Id);
        sensor1Data.Readings.Should().HaveCount(1);

        var sensor2Data = result.Sensors.First(s => s.SensorId == sensor2Id);
        sensor2Data.Readings.Should().BeEmpty();

        var sensor3Data = result.Sensors.First(s => s.SensorId == sensor3Id);
        sensor3Data.Readings.Should().HaveCount(LargeDatasetReadings);
    }

    [Fact]
    public async Task HandleAsync_ShouldPreserveOrderOfSensors()
    {
        // Given
        var from = DateTimeOffset.UtcNow.AddHours(-1);
        var to = DateTimeOffset.UtcNow;

        var sensorIds = Enumerable.Range(1, 5)
            .Select(i => SensorId.From($"sensor-{i}"))
            .ToList();

        var sensors = sensorIds
            .Select(id => new SensorInfo(id, $"Name-{id.Value}", $"Label-{id.Value}", "address", "DefaultSensorType", true, null))
            .ToList();

        _sensorRepository
            .GetAllActiveAsync(Arg.Any<CancellationToken>())
            .Returns(sensors);

        _temperatureRepository
            .GetHistoryBatchAsync(
                Arg.Any<IReadOnlyList<SensorId>>(),
                from,
                to,
                Arg.Any<CancellationToken>())
            .Returns(new Dictionary<SensorId, IReadOnlyList<SensorReading>>());

        // When
        var result = await _handler.HandleAsync(new GetAllSensorsHistory.Query(from, to));

        // Then
        result.Sensors.Should().HaveCount(5);
        for (var i = 0; i < 5; i++)
        {
            result.Sensors[i].SensorId.Should().Be(sensorIds[i]);
        }
    }
}
