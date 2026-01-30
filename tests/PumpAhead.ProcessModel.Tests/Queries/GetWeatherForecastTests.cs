using FluentAssertions;
using NSubstitute;
using PumpAhead.UseCases.Ports.Out;
using PumpAhead.UseCases.Queries.GetWeatherForecast;

namespace PumpAhead.ProcessModel.Tests.Queries;

public class GetWeatherForecastTests
{
    private const int DefaultForecastHours = 12;
    private const int CustomForecastHours = 24;
    private const int ShortForecastHours = 6;
    private const decimal Temperature15_5 = 15.5m;
    private const decimal Temperature16 = 16.0m;
    private const decimal Temperature14_5 = 14.5m;
    private const decimal Temperature20 = 20.0m;
    private const decimal Temperature21 = 21.0m;
    private const decimal Temperature10 = 10.0m;
    private const decimal Temperature11 = 11.0m;
    private const decimal Temperature12 = 12.0m;
    private const decimal Temperature13 = 13.0m;
    private const decimal Temperature15 = 15.0m;
    private const decimal Temperature17 = 17.0m;
    private const decimal Temperature25_5 = 25.5m;

    private readonly IWeatherForecastRepository _repository;
    private readonly GetWeatherForecast.Handler _handler;

    public GetWeatherForecastTests()
    {
        _repository = Substitute.For<IWeatherForecastRepository>();
        _handler = new GetWeatherForecast.Handler(_repository);
    }

    #region Given-When-Then: Empty forecast list

    [Fact]
    public async Task HandleAsync_GivenNoForecastData_WhenQueryingForForecast_ThenReturnsEmptyList()
    {
        // Given
        var from = DateTimeOffset.UtcNow;
        var hours = DefaultForecastHours;

        _repository
            .GetForecastFromAsync(from, hours, Arg.Any<CancellationToken>())
            .Returns(new List<WeatherForecastPoint>());

        // When
        var result = await _handler.HandleAsync(new GetWeatherForecast.Query(from, hours));

        // Then
        result.Should().NotBeNull();
        result.Points.Should().BeEmpty();
    }

    #endregion

    #region Given-When-Then: Forecast data in time range

    [Fact]
    public async Task HandleAsync_GivenForecastDataExists_WhenQueryingForForecast_ThenReturnsForecastPoints()
    {
        // Given
        var from = DateTimeOffset.UtcNow;
        var hours = DefaultForecastHours;
        var timestamp1 = from.AddHours(1);
        var timestamp2 = from.AddHours(2);
        var timestamp3 = from.AddHours(3);

        var forecastPoints = new List<WeatherForecastPoint>
        {
            new(Temperature15_5, timestamp1),
            new(Temperature16, timestamp2),
            new(Temperature14_5, timestamp3)
        };

        _repository
            .GetForecastFromAsync(from, hours, Arg.Any<CancellationToken>())
            .Returns(forecastPoints);

        // When
        var result = await _handler.HandleAsync(new GetWeatherForecast.Query(from, hours));

        // Then
        result.Should().NotBeNull();
        result.Points.Should().HaveCount(3);
        result.Points[0].TemperatureCelsius.Should().Be(Temperature15_5);
        result.Points[1].TemperatureCelsius.Should().Be(Temperature16);
        result.Points[2].TemperatureCelsius.Should().Be(Temperature14_5);
    }

    [Fact]
    public async Task HandleAsync_GivenForecastDataExists_WhenQueryingForForecast_ThenPreservesTimestamps()
    {
        // Given
        var from = DateTimeOffset.UtcNow;
        var hours = ShortForecastHours;
        var timestamp1 = from.AddHours(1);
        var timestamp2 = from.AddHours(2);

        var forecastPoints = new List<WeatherForecastPoint>
        {
            new(Temperature20, timestamp1),
            new(Temperature21, timestamp2)
        };

        _repository
            .GetForecastFromAsync(from, hours, Arg.Any<CancellationToken>())
            .Returns(forecastPoints);

        // When
        var result = await _handler.HandleAsync(new GetWeatherForecast.Query(from, hours));

        // Then
        result.Points[0].Timestamp.Should().Be(timestamp1);
        result.Points[1].Timestamp.Should().Be(timestamp2);
    }

    [Fact]
    public async Task HandleAsync_GivenDifferentHoursParameter_WhenQueryingForForecast_ThenPassesCorrectHoursToRepository()
    {
        // Given
        var from = DateTimeOffset.UtcNow;
        var customHours = CustomForecastHours;

        _repository
            .GetForecastFromAsync(from, customHours, Arg.Any<CancellationToken>())
            .Returns(new List<WeatherForecastPoint>());

        // When
        await _handler.HandleAsync(new GetWeatherForecast.Query(from, customHours));

        // Then
        await _repository.Received(1).GetForecastFromAsync(from, customHours, Arg.Any<CancellationToken>());
    }

    #endregion

    #region Given-When-Then: Sorting verification

    [Fact]
    public async Task HandleAsync_GivenForecastPointsFromRepository_WhenQueryingForForecast_ThenMaintainsRepositoryOrder()
    {
        // Given
        var from = DateTimeOffset.UtcNow;
        var hours = DefaultForecastHours;

        var forecastPoints = new List<WeatherForecastPoint>
        {
            new(Temperature10, from.AddHours(1)),
            new(Temperature12, from.AddHours(2)),
            new(Temperature11, from.AddHours(3)),
            new(Temperature13, from.AddHours(4))
        };

        _repository
            .GetForecastFromAsync(from, hours, Arg.Any<CancellationToken>())
            .Returns(forecastPoints);

        // When
        var result = await _handler.HandleAsync(new GetWeatherForecast.Query(from, hours));

        // Then
        result.Points.Should().HaveCount(4);
        result.Points.Select(p => p.TemperatureCelsius)
            .Should().ContainInOrder(Temperature10, Temperature12, Temperature11, Temperature13);
    }

    [Fact]
    public async Task HandleAsync_GivenForecastPointsSortedByTimestamp_WhenQueryingForForecast_ThenResultsAreSortedChronologically()
    {
        // Given
        var from = DateTimeOffset.UtcNow;
        var hours = DefaultForecastHours;
        var timestamp1 = from.AddHours(1);
        var timestamp2 = from.AddHours(2);
        var timestamp3 = from.AddHours(3);

        var forecastPoints = new List<WeatherForecastPoint>
        {
            new(Temperature15, timestamp1),
            new(Temperature16, timestamp2),
            new(Temperature17, timestamp3)
        };

        _repository
            .GetForecastFromAsync(from, hours, Arg.Any<CancellationToken>())
            .Returns(forecastPoints);

        // When
        var result = await _handler.HandleAsync(new GetWeatherForecast.Query(from, hours));

        // Then
        result.Points.Select(p => p.Timestamp)
            .Should().BeInAscendingOrder();
    }

    #endregion

    #region Given-When-Then: Default hours parameter

    [Fact]
    public async Task HandleAsync_GivenQueryWithDefaultHours_WhenQueryingForForecast_ThenUsesDefaultValue()
    {
        // Given
        var from = DateTimeOffset.UtcNow;
        var query = new GetWeatherForecast.Query(from); // uses default Hours = DefaultForecastHours

        _repository
            .GetForecastFromAsync(from, DefaultForecastHours, Arg.Any<CancellationToken>())
            .Returns(new List<WeatherForecastPoint>());

        // When
        await _handler.HandleAsync(query);

        // Then
        await _repository.Received(1).GetForecastFromAsync(from, DefaultForecastHours, Arg.Any<CancellationToken>());
    }

    #endregion

    #region Given-When-Then: Data mapping verification

    [Fact]
    public async Task HandleAsync_GivenRepositoryReturnsWeatherForecastPoints_WhenQueryingForForecast_ThenMapsToForecastPointsCorrectly()
    {
        // Given
        var from = DateTimeOffset.UtcNow;
        var hours = DefaultForecastHours;
        var timestamp = from.AddHours(5);
        var temperature = Temperature25_5;

        var repositoryPoints = new List<WeatherForecastPoint>
        {
            new(temperature, timestamp)
        };

        _repository
            .GetForecastFromAsync(from, hours, Arg.Any<CancellationToken>())
            .Returns(repositoryPoints);

        // When
        var result = await _handler.HandleAsync(new GetWeatherForecast.Query(from, hours));

        // Then
        result.Points.Should().ContainSingle()
            .Which.Should().Match<GetWeatherForecast.ForecastPoint>(p =>
                p.TemperatureCelsius == temperature &&
                p.Timestamp == timestamp);
    }

    #endregion
}
