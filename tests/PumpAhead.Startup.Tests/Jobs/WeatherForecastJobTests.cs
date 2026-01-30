using FluentAssertions;
using Microsoft.AspNetCore.SignalR;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using NSubstitute;
using NSubstitute.ExceptionExtensions;
using PumpAhead.Adapters.Gui.Hubs;
using PumpAhead.Adapters.Gui.Services;
using PumpAhead.Startup.Jobs;
using PumpAhead.UseCases.Ports.Out;
using Quartz;

namespace PumpAhead.Startup.Tests.Jobs;

public class WeatherForecastJobTests
{
    private const double DefaultLatitude = 50.71;
    private const double DefaultLongitude = 17.34;
    private const int DefaultForecastHours = 24;
    private const decimal BaseTemperatureCelsius = 15m;
    private const decimal FirstPointTemperatureCelsius = 15.5m;
    private const decimal SecondPointTemperatureCelsius = 16.0m;
    private const decimal ThirdPointTemperatureCelsius = 14.5m;
    private const int ThreePoints = 3;
    private const string WeatherApiUnavailableMessage = "Weather API unavailable";
    private const string DatabaseConnectionFailedMessage = "Database connection failed";
    private const string SignalRConnectionFailedMessage = "SignalR connection failed";
    private const string ApiErrorMessage = "API error";

    private readonly IWeatherForecastProvider _weatherProvider;
    private readonly IWeatherForecastRepository _weatherRepository;
    private readonly IHubContext<SensorHub, ISensorHubClient> _hubContext;
    private readonly ISensorHubClient _allClients;
    private readonly IOptions<WeatherSettings> _settings;
    private readonly ILogger<WeatherForecastJob> _logger;
    private readonly IJobExecutionContext _jobContext;
    private readonly WeatherForecastJob _sut;

    public WeatherForecastJobTests()
    {
        _weatherProvider = Substitute.For<IWeatherForecastProvider>();
        _weatherRepository = Substitute.For<IWeatherForecastRepository>();
        _hubContext = Substitute.For<IHubContext<SensorHub, ISensorHubClient>>();
        _allClients = Substitute.For<ISensorHubClient>();
        _hubContext.Clients.All.Returns(_allClients);
        _settings = Options.Create(new WeatherSettings
        {
            Latitude = DefaultLatitude,
            Longitude = DefaultLongitude,
            ForecastHours = DefaultForecastHours
        });
        _logger = Substitute.For<ILogger<WeatherForecastJob>>();
        _jobContext = Substitute.For<IJobExecutionContext>();
        _jobContext.CancellationToken.Returns(CancellationToken.None);

        _sut = new WeatherForecastJob(
            _weatherProvider,
            _weatherRepository,
            _hubContext,
            _settings,
            _logger);
    }

    #region Execute - Provider Invocation

    [Fact]
    public async Task Execute_GivenValidSettings_WhenInvoked_ThenCallsProviderWithCorrectParameters()
    {
        // Given
        var forecast = CreateForecast(ThreePoints);
        _weatherProvider.GetForecastAsync(
                Arg.Any<double>(), Arg.Any<double>(), Arg.Any<int>(), Arg.Any<CancellationToken>())
            .Returns(forecast);

        // When
        await _sut.Execute(_jobContext);

        // Then
        await _weatherProvider.Received(1).GetForecastAsync(
            _settings.Value.Latitude,
            _settings.Value.Longitude,
            _settings.Value.ForecastHours,
            _jobContext.CancellationToken);
    }

    [Fact]
    public async Task Execute_GivenCancellationToken_WhenInvoked_ThenPassesCancellationTokenToProvider()
    {
        // Given
        var cts = new CancellationTokenSource();
        _jobContext.CancellationToken.Returns(cts.Token);
        var forecast = CreateForecast(1);
        _weatherProvider.GetForecastAsync(
                Arg.Any<double>(), Arg.Any<double>(), Arg.Any<int>(), Arg.Any<CancellationToken>())
            .Returns(forecast);

        // When
        await _sut.Execute(_jobContext);

        // Then
        await _weatherProvider.Received(1).GetForecastAsync(
            Arg.Any<double>(),
            Arg.Any<double>(),
            Arg.Any<int>(),
            cts.Token);
    }

    #endregion

    #region Execute - Repository Saving

    [Fact]
    public async Task Execute_GivenForecastWithPoints_WhenInvoked_ThenSavesForecastToRepository()
    {
        // Given
        var fetchedAt = DateTimeOffset.UtcNow;
        var points = new List<WeatherForecastPoint>
        {
            new(FirstPointTemperatureCelsius, DateTimeOffset.UtcNow.AddHours(1)),
            new(SecondPointTemperatureCelsius, DateTimeOffset.UtcNow.AddHours(2)),
            new(ThirdPointTemperatureCelsius, DateTimeOffset.UtcNow.AddHours(3))
        };
        var forecast = new WeatherForecast(points, fetchedAt);

        _weatherProvider.GetForecastAsync(
                Arg.Any<double>(), Arg.Any<double>(), Arg.Any<int>(), Arg.Any<CancellationToken>())
            .Returns(forecast);

        // When
        await _sut.Execute(_jobContext);

        // Then
        await _weatherRepository.Received(1).SaveForecastAsync(
            Arg.Is<IReadOnlyList<WeatherForecastPoint>>(p => p.Count == ThreePoints),
            fetchedAt,
            Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task Execute_GivenForecastWithEmptyPoints_WhenInvoked_ThenDoesNotSaveToRepository()
    {
        // Given
        var forecast = new WeatherForecast(new List<WeatherForecastPoint>(), DateTimeOffset.UtcNow);
        _weatherProvider.GetForecastAsync(
                Arg.Any<double>(), Arg.Any<double>(), Arg.Any<int>(), Arg.Any<CancellationToken>())
            .Returns(forecast);

        // When
        await _sut.Execute(_jobContext);

        // Then
        await _weatherRepository.DidNotReceive().SaveForecastAsync(
            Arg.Any<IReadOnlyList<WeatherForecastPoint>>(),
            Arg.Any<DateTimeOffset>(),
            Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task Execute_GivenNullForecast_WhenInvoked_ThenDoesNotSaveToRepository()
    {
        // Given
        _weatherProvider.GetForecastAsync(
                Arg.Any<double>(), Arg.Any<double>(), Arg.Any<int>(), Arg.Any<CancellationToken>())
            .Returns((WeatherForecast?)null);

        // When
        await _sut.Execute(_jobContext);

        // Then
        await _weatherRepository.DidNotReceive().SaveForecastAsync(
            Arg.Any<IReadOnlyList<WeatherForecastPoint>>(),
            Arg.Any<DateTimeOffset>(),
            Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task Execute_GivenValidForecast_WhenSaved_ThenNotifiesClientsViaHub()
    {
        // Given
        var forecast = CreateForecast(5);
        _weatherProvider.GetForecastAsync(
                Arg.Any<double>(), Arg.Any<double>(), Arg.Any<int>(), Arg.Any<CancellationToken>())
            .Returns(forecast);

        // When
        await _sut.Execute(_jobContext);

        // Then
        await _allClients.Received(1).ReceiveWeatherForecastUpdate();
    }

    [Fact]
    public async Task Execute_GivenEmptyForecast_WhenInvoked_ThenDoesNotNotifyClients()
    {
        // Given
        var forecast = new WeatherForecast(new List<WeatherForecastPoint>(), DateTimeOffset.UtcNow);
        _weatherProvider.GetForecastAsync(
                Arg.Any<double>(), Arg.Any<double>(), Arg.Any<int>(), Arg.Any<CancellationToken>())
            .Returns(forecast);

        // When
        await _sut.Execute(_jobContext);

        // Then
        await _allClients.DidNotReceive().ReceiveWeatherForecastUpdate();
    }

    #endregion

    #region Execute - Error Handling

    [Fact]
    public async Task Execute_GivenProviderThrowsException_WhenInvoked_ThenLogsWarningAndDoesNotRethrow()
    {
        // Given
        var exception = new HttpRequestException(WeatherApiUnavailableMessage);
        _weatherProvider.GetForecastAsync(
                Arg.Any<double>(), Arg.Any<double>(), Arg.Any<int>(), Arg.Any<CancellationToken>())
            .ThrowsAsync(exception);

        // When
        var act = () => _sut.Execute(_jobContext);

        // Then
        await act.Should().NotThrowAsync();
        _logger.Received(1).Log(
            LogLevel.Warning,
            Arg.Any<EventId>(),
            Arg.Any<object>(),
            exception,
            Arg.Any<Func<object, Exception?, string>>());
    }

    [Fact]
    public async Task Execute_GivenRepositoryThrowsException_WhenInvoked_ThenLogsWarningAndDoesNotRethrow()
    {
        // Given
        var forecast = CreateForecast(ThreePoints);
        _weatherProvider.GetForecastAsync(
                Arg.Any<double>(), Arg.Any<double>(), Arg.Any<int>(), Arg.Any<CancellationToken>())
            .Returns(forecast);

        var exception = new InvalidOperationException(DatabaseConnectionFailedMessage);
        _weatherRepository.SaveForecastAsync(
                Arg.Any<IReadOnlyList<WeatherForecastPoint>>(),
                Arg.Any<DateTimeOffset>(),
                Arg.Any<CancellationToken>())
            .ThrowsAsync(exception);

        // When
        var act = () => _sut.Execute(_jobContext);

        // Then
        await act.Should().NotThrowAsync();
        _logger.Received(1).Log(
            LogLevel.Warning,
            Arg.Any<EventId>(),
            Arg.Any<object>(),
            exception,
            Arg.Any<Func<object, Exception?, string>>());
    }

    [Fact]
    public async Task Execute_GivenHubThrowsException_WhenInvoked_ThenLogsWarningAndDoesNotRethrow()
    {
        // Given
        var forecast = CreateForecast(ThreePoints);
        _weatherProvider.GetForecastAsync(
                Arg.Any<double>(), Arg.Any<double>(), Arg.Any<int>(), Arg.Any<CancellationToken>())
            .Returns(forecast);

        var exception = new InvalidOperationException(SignalRConnectionFailedMessage);
        _allClients.ReceiveWeatherForecastUpdate()
            .Returns(Task.FromException(exception));

        // When
        var act = () => _sut.Execute(_jobContext);

        // Then
        await act.Should().NotThrowAsync();
        _logger.Received(1).Log(
            LogLevel.Warning,
            Arg.Any<EventId>(),
            Arg.Any<object>(),
            exception,
            Arg.Any<Func<object, Exception?, string>>());
    }

    [Fact]
    public async Task Execute_GivenProviderThrowsException_WhenInvoked_ThenDoesNotSaveToRepository()
    {
        // Given
        _weatherProvider.GetForecastAsync(
                Arg.Any<double>(), Arg.Any<double>(), Arg.Any<int>(), Arg.Any<CancellationToken>())
            .ThrowsAsync(new HttpRequestException(ApiErrorMessage));

        // When
        await _sut.Execute(_jobContext);

        // Then
        await _weatherRepository.DidNotReceive().SaveForecastAsync(
            Arg.Any<IReadOnlyList<WeatherForecastPoint>>(),
            Arg.Any<DateTimeOffset>(),
            Arg.Any<CancellationToken>());
    }

    #endregion

    #region Execute - Logging Success

    [Fact]
    public async Task Execute_GivenSuccessfulForecastUpdate_WhenInvoked_ThenLogsInformationWithPointCount()
    {
        // Given
        var forecast = CreateForecast(5);
        _weatherProvider.GetForecastAsync(
                Arg.Any<double>(), Arg.Any<double>(), Arg.Any<int>(), Arg.Any<CancellationToken>())
            .Returns(forecast);

        // When
        await _sut.Execute(_jobContext);

        // Then
        _logger.Received(1).Log(
            LogLevel.Information,
            Arg.Any<EventId>(),
            Arg.Any<object>(),
            Arg.Is<Exception?>(e => e == null),
            Arg.Any<Func<object, Exception?, string>>());
    }

    #endregion

    #region Helper Methods

    private static WeatherForecast CreateForecast(int pointCount)
    {
        var points = Enumerable.Range(1, pointCount)
            .Select(i => new WeatherForecastPoint(BaseTemperatureCelsius + i, DateTimeOffset.UtcNow.AddHours(i)))
            .ToList();
        return new WeatherForecast(points, DateTimeOffset.UtcNow);
    }

    #endregion
}
