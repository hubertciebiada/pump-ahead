using System.Net;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using NSubstitute;
using PumpAhead.Adapters.Out.Weather;
using PumpAhead.UseCases.Ports.Out;
using RichardSzalay.MockHttp;

namespace PumpAhead.Adapters.Out.Tests.Weather;

public class OpenMeteoWeatherProviderTests
{
    private const double TestLatitude = 52.2297;
    private const double TestLongitude = 21.0122;
    private const int DefaultForecastHours = 12;
    private const int CustomForecastHours = 24;
    private const string OpenMeteoApiUrl = "https://api.open-meteo.com/v1/forecast*";
    private const string ApplicationJson = "application/json";
    private const decimal Temperature1 = 5.2m;
    private const decimal Temperature2 = 6.8m;
    private const decimal Temperature3 = 7.1m;
    private const decimal NegativeTemperature1 = -5.5m;
    private const decimal NegativeTemperature2 = -12.3m;
    private const decimal HighTemperature = 38.7m;
    private const decimal ZeroTemperature = 0m;

    private readonly MockHttpMessageHandler _mockHttp;
    private readonly ILogger<OpenMeteoWeatherProvider> _logger;
    private readonly OpenMeteoWeatherProvider _sut;

    public OpenMeteoWeatherProviderTests()
    {
        _mockHttp = new MockHttpMessageHandler();
        _logger = Substitute.For<ILogger<OpenMeteoWeatherProvider>>();

        var httpClient = _mockHttp.ToHttpClient();
        _sut = new OpenMeteoWeatherProvider(httpClient, _logger);
    }

    #region Given valid JSON response - successful forecast retrieval

    [Fact]
    public async Task GetForecastAsync_GivenValidJsonResponse_WhenCalled_ThenReturnsNonNullForecast()
    {
        // Given
        var jsonResponse = CreateValidJsonResponse();
        _mockHttp
            .When(OpenMeteoApiUrl)
            .Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.GetForecastAsync(TestLatitude, TestLongitude);

        // Then
        result.Should().NotBeNull();
    }

    [Fact]
    public async Task GetForecastAsync_GivenValidJsonResponse_WhenCalled_ThenReturnsCorrectNumberOfForecastPoints()
    {
        // Given
        var jsonResponse = CreateValidJsonResponse();
        _mockHttp
            .When(OpenMeteoApiUrl)
            .Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.GetForecastAsync(TestLatitude, TestLongitude);

        // Then
        result!.HourlyPoints.Should().HaveCount(3);
    }

    [Fact]
    public async Task GetForecastAsync_GivenValidJsonResponse_WhenCalled_ThenMapsTemperaturesCorrectly()
    {
        // Given
        var jsonResponse = CreateValidJsonResponse();
        _mockHttp
            .When(OpenMeteoApiUrl)
            .Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.GetForecastAsync(TestLatitude, TestLongitude);

        // Then
        result!.HourlyPoints[0].TemperatureCelsius.Should().Be(Temperature1);
        result.HourlyPoints[1].TemperatureCelsius.Should().Be(Temperature2);
        result.HourlyPoints[2].TemperatureCelsius.Should().Be(Temperature3);
    }

    [Fact]
    public async Task GetForecastAsync_GivenValidJsonResponse_WhenCalled_ThenMapsTimestampsCorrectly()
    {
        // Given
        var jsonResponse = CreateValidJsonResponse();
        _mockHttp
            .When(OpenMeteoApiUrl)
            .Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.GetForecastAsync(TestLatitude, TestLongitude);

        // Then
        result!.HourlyPoints[0].ForecastTimestamp.Should().Be(DateTimeOffset.Parse("2024-01-15T10:00"));
        result.HourlyPoints[1].ForecastTimestamp.Should().Be(DateTimeOffset.Parse("2024-01-15T11:00"));
        result.HourlyPoints[2].ForecastTimestamp.Should().Be(DateTimeOffset.Parse("2024-01-15T12:00"));
    }

    [Fact]
    public async Task GetForecastAsync_GivenValidJsonResponse_WhenCalled_ThenSetsFetchedAtToCurrentTime()
    {
        // Given
        var jsonResponse = CreateValidJsonResponse();
        _mockHttp
            .When(OpenMeteoApiUrl)
            .Respond(ApplicationJson, jsonResponse);
        var beforeCall = DateTimeOffset.UtcNow;

        // When
        var result = await _sut.GetForecastAsync(TestLatitude, TestLongitude);

        // Then
        var afterCall = DateTimeOffset.UtcNow;
        result!.FetchedAt.Should().BeOnOrAfter(beforeCall);
        result.FetchedAt.Should().BeOnOrBefore(afterCall);
    }

    [Fact]
    public async Task GetForecastAsync_GivenNegativeTemperatures_WhenCalled_ThenMapsCorrectly()
    {
        // Given
        var jsonResponse = """
            {
                "hourly": {
                    "time": ["2024-01-15T10:00", "2024-01-15T11:00"],
                    "temperature_2m": [-5.5, -12.3]
                }
            }
            """;
        _mockHttp
            .When(OpenMeteoApiUrl)
            .Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.GetForecastAsync(TestLatitude, TestLongitude);

        // Then
        result!.HourlyPoints[0].TemperatureCelsius.Should().Be(NegativeTemperature1);
        result.HourlyPoints[1].TemperatureCelsius.Should().Be(NegativeTemperature2);
    }

    [Fact]
    public async Task GetForecastAsync_GivenHighTemperatures_WhenCalled_ThenMapsCorrectly()
    {
        // Given
        var jsonResponse = """
            {
                "hourly": {
                    "time": ["2024-07-15T14:00"],
                    "temperature_2m": [38.7]
                }
            }
            """;
        _mockHttp
            .When(OpenMeteoApiUrl)
            .Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.GetForecastAsync(TestLatitude, TestLongitude);

        // Then
        result!.HourlyPoints[0].TemperatureCelsius.Should().Be(HighTemperature);
    }

    #endregion

    #region Given valid JSON response - URL construction

    [Fact]
    public async Task GetForecastAsync_GivenCoordinates_WhenCalled_ThenBuildsCorrectUrl()
    {
        // Given
        var jsonResponse = CreateValidJsonResponse();
        var expectedUrlPattern = $"https://api.open-meteo.com/v1/forecast?latitude={TestLatitude.ToString(System.Globalization.CultureInfo.InvariantCulture)}&longitude={TestLongitude.ToString(System.Globalization.CultureInfo.InvariantCulture)}&hourly=temperature_2m&forecast_hours={DefaultForecastHours}&timezone=auto";

        _mockHttp
            .Expect(expectedUrlPattern)
            .Respond("application/json", jsonResponse);

        // When
        await _sut.GetForecastAsync(TestLatitude, TestLongitude);

        // Then
        _mockHttp.VerifyNoOutstandingExpectation();
    }

    [Fact]
    public async Task GetForecastAsync_GivenCustomForecastHours_WhenCalled_ThenBuildsCorrectUrl()
    {
        // Given
        var jsonResponse = CreateValidJsonResponse();

        _mockHttp
            .Expect($"https://api.open-meteo.com/v1/forecast?latitude={TestLatitude.ToString(System.Globalization.CultureInfo.InvariantCulture)}&longitude={TestLongitude.ToString(System.Globalization.CultureInfo.InvariantCulture)}&hourly=temperature_2m&forecast_hours={CustomForecastHours}&timezone=auto")
            .Respond(ApplicationJson, jsonResponse);

        // When
        await _sut.GetForecastAsync(TestLatitude, TestLongitude, forecastHours: CustomForecastHours);

        // Then
        _mockHttp.VerifyNoOutstandingExpectation();
    }

    [Fact]
    public async Task GetForecastAsync_GivenDecimalCoordinatesWithPrecision_WhenCalled_ThenFormatsWithInvariantCulture()
    {
        // Given
        var jsonResponse = CreateValidJsonResponse();

        _mockHttp
            .Expect($"https://api.open-meteo.com/v1/forecast?latitude=52.2297&longitude=21.0122&hourly=temperature_2m&forecast_hours={DefaultForecastHours}&timezone=auto")
            .Respond(ApplicationJson, jsonResponse);

        // When
        await _sut.GetForecastAsync(TestLatitude, TestLongitude);

        // Then
        _mockHttp.VerifyNoOutstandingExpectation();
    }

    #endregion

    #region Given HTTP errors - graceful error handling

    [Fact]
    public async Task GetForecastAsync_GivenHttpNotFoundError_WhenCalled_ThenReturnsNull()
    {
        // Given
        _mockHttp
            .When(OpenMeteoApiUrl)
            .Respond(HttpStatusCode.NotFound);

        // When
        var result = await _sut.GetForecastAsync(TestLatitude, TestLongitude);

        // Then
        result.Should().BeNull();
    }

    [Fact]
    public async Task GetForecastAsync_GivenHttpInternalServerError_WhenCalled_ThenReturnsNull()
    {
        // Given
        _mockHttp
            .When(OpenMeteoApiUrl)
            .Respond(HttpStatusCode.InternalServerError);

        // When
        var result = await _sut.GetForecastAsync(TestLatitude, TestLongitude);

        // Then
        result.Should().BeNull();
    }

    [Fact]
    public async Task GetForecastAsync_GivenHttpServiceUnavailable_WhenCalled_ThenReturnsNull()
    {
        // Given
        _mockHttp
            .When(OpenMeteoApiUrl)
            .Respond(HttpStatusCode.ServiceUnavailable);

        // When
        var result = await _sut.GetForecastAsync(TestLatitude, TestLongitude);

        // Then
        result.Should().BeNull();
    }

    [Fact]
    public async Task GetForecastAsync_GivenHttpBadRequest_WhenCalled_ThenReturnsNull()
    {
        // Given
        _mockHttp
            .When(OpenMeteoApiUrl)
            .Respond(HttpStatusCode.BadRequest);

        // When
        var result = await _sut.GetForecastAsync(TestLatitude, TestLongitude);

        // Then
        result.Should().BeNull();
    }

    [Fact]
    public async Task GetForecastAsync_GivenHttpTooManyRequests_WhenCalled_ThenReturnsNull()
    {
        // Given
        _mockHttp
            .When(OpenMeteoApiUrl)
            .Respond(HttpStatusCode.TooManyRequests);

        // When
        var result = await _sut.GetForecastAsync(TestLatitude, TestLongitude);

        // Then
        result.Should().BeNull();
    }

    [Fact]
    public async Task GetForecastAsync_GivenConnectionRefused_WhenCalled_ThenReturnsNull()
    {
        // Given
        _mockHttp
            .When(OpenMeteoApiUrl)
            .Throw(new HttpRequestException("Connection refused"));

        // When
        var result = await _sut.GetForecastAsync(TestLatitude, TestLongitude);

        // Then
        result.Should().BeNull();
    }

    [Fact]
    public async Task GetForecastAsync_GivenNetworkError_WhenCalled_ThenReturnsNull()
    {
        // Given
        _mockHttp
            .When(OpenMeteoApiUrl)
            .Throw(new HttpRequestException("No such host is known"));

        // When
        var result = await _sut.GetForecastAsync(TestLatitude, TestLongitude);

        // Then
        result.Should().BeNull();
    }

    #endregion

    #region Given timeout - graceful handling

    [Fact]
    public async Task GetForecastAsync_GivenTimeout_WhenCalled_ThenReturnsNull()
    {
        // Given
        _mockHttp
            .When(OpenMeteoApiUrl)
            .Throw(new TaskCanceledException("Request timed out", new TimeoutException()));

        // When
        var result = await _sut.GetForecastAsync(TestLatitude, TestLongitude);

        // Then
        result.Should().BeNull();
    }

    [Fact]
    public async Task GetForecastAsync_GivenOperationCanceled_WhenCalled_ThenReturnsNull()
    {
        // Given
        using var cts = new CancellationTokenSource();
        await cts.CancelAsync();

        _mockHttp
            .When(OpenMeteoApiUrl)
            .Throw(new TaskCanceledException("Operation canceled", null, cts.Token));

        // When
        var result = await _sut.GetForecastAsync(TestLatitude, TestLongitude, cancellationToken: cts.Token);

        // Then
        result.Should().BeNull();
    }

    #endregion

    #region Given invalid JSON - graceful handling

    [Fact]
    public async Task GetForecastAsync_GivenInvalidJson_WhenCalled_ThenReturnsNull()
    {
        // Given
        _mockHttp
            .When(OpenMeteoApiUrl)
            .Respond(ApplicationJson, "not valid json {{{");

        // When
        var result = await _sut.GetForecastAsync(TestLatitude, TestLongitude);

        // Then
        result.Should().BeNull();
    }

    [Fact]
    public async Task GetForecastAsync_GivenEmptyJsonObject_WhenCalled_ThenReturnsNull()
    {
        // Given
        _mockHttp
            .When(OpenMeteoApiUrl)
            .Respond(ApplicationJson, "{}");

        // When
        var result = await _sut.GetForecastAsync(TestLatitude, TestLongitude);

        // Then
        result.Should().BeNull();
    }

    [Fact]
    public async Task GetForecastAsync_GivenNullHourlyData_WhenCalled_ThenReturnsNull()
    {
        // Given
        _mockHttp
            .When(OpenMeteoApiUrl)
            .Respond(ApplicationJson, """{"hourly": null}""");

        // When
        var result = await _sut.GetForecastAsync(TestLatitude, TestLongitude);

        // Then
        result.Should().BeNull();
    }

    [Fact]
    public async Task GetForecastAsync_GivenEmptyResponse_WhenCalled_ThenReturnsNull()
    {
        // Given
        _mockHttp
            .When(OpenMeteoApiUrl)
            .Respond(ApplicationJson, "");

        // When
        var result = await _sut.GetForecastAsync(TestLatitude, TestLongitude);

        // Then
        result.Should().BeNull();
    }

    [Fact]
    public async Task GetForecastAsync_GivenMissingHourlyField_WhenCalled_ThenReturnsNull()
    {
        // Given
        var jsonResponse = """
            {
                "latitude": 52.52,
                "longitude": 13.405
            }
            """;
        _mockHttp
            .When(OpenMeteoApiUrl)
            .Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.GetForecastAsync(TestLatitude, TestLongitude);

        // Then
        result.Should().BeNull();
    }

    #endregion

    #region Given edge cases in data mapping

    [Fact]
    public async Task GetForecastAsync_GivenEmptyTimeAndTemperatureArrays_WhenCalled_ThenReturnsEmptyForecastPoints()
    {
        // Given
        var jsonResponse = """
            {
                "hourly": {
                    "time": [],
                    "temperature_2m": []
                }
            }
            """;
        _mockHttp
            .When(OpenMeteoApiUrl)
            .Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.GetForecastAsync(TestLatitude, TestLongitude);

        // Then
        result.Should().NotBeNull();
        result!.HourlyPoints.Should().BeEmpty();
    }

    [Fact]
    public async Task GetForecastAsync_GivenMoreTimesThanTemperatures_WhenCalled_ThenMapsOnlyMatchingPairs()
    {
        // Given
        var jsonResponse = """
            {
                "hourly": {
                    "time": ["2024-01-15T10:00", "2024-01-15T11:00", "2024-01-15T12:00"],
                    "temperature_2m": [5.0, 6.0]
                }
            }
            """;
        _mockHttp
            .When(OpenMeteoApiUrl)
            .Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.GetForecastAsync(TestLatitude, TestLongitude);

        // Then
        result!.HourlyPoints.Should().HaveCount(2);
        result.HourlyPoints[0].TemperatureCelsius.Should().Be(5.0m);
        result.HourlyPoints[1].TemperatureCelsius.Should().Be(6.0m);
    }

    [Fact]
    public async Task GetForecastAsync_GivenInvalidTimestamp_WhenCalled_ThenSkipsInvalidEntry()
    {
        // Given
        var jsonResponse = """
            {
                "hourly": {
                    "time": ["invalid-date", "2024-01-15T11:00"],
                    "temperature_2m": [5.0, 6.0]
                }
            }
            """;
        _mockHttp
            .When(OpenMeteoApiUrl)
            .Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.GetForecastAsync(TestLatitude, TestLongitude);

        // Then
        result!.HourlyPoints.Should().HaveCount(1);
        result.HourlyPoints[0].TemperatureCelsius.Should().Be(6.0m);
    }

    [Fact]
    public async Task GetForecastAsync_GivenISO8601TimestampWithTimezone_WhenCalled_ThenParsesCorrectly()
    {
        // Given
        var jsonResponse = """
            {
                "hourly": {
                    "time": ["2024-01-15T10:00+01:00"],
                    "temperature_2m": [5.0]
                }
            }
            """;
        _mockHttp
            .When(OpenMeteoApiUrl)
            .Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.GetForecastAsync(TestLatitude, TestLongitude);

        // Then
        result!.HourlyPoints.Should().HaveCount(1);
        result.HourlyPoints[0].ForecastTimestamp.Offset.Should().Be(TimeSpan.FromHours(1));
    }

    [Fact]
    public async Task GetForecastAsync_GivenZeroTemperature_WhenCalled_ThenMapsCorrectly()
    {
        // Given
        var jsonResponse = """
            {
                "hourly": {
                    "time": ["2024-01-15T10:00"],
                    "temperature_2m": [0.0]
                }
            }
            """;
        _mockHttp
            .When(OpenMeteoApiUrl)
            .Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.GetForecastAsync(TestLatitude, TestLongitude);

        // Then
        result!.HourlyPoints[0].TemperatureCelsius.Should().Be(ZeroTemperature);
    }

    [Fact]
    public async Task GetForecastAsync_GivenLargeDataset_WhenCalled_ThenMapsAllPoints()
    {
        // Given - 48 hours of forecast data
        var times = Enumerable.Range(0, 48)
            .Select(i => $"\"2024-01-15T{i % 24:D2}:00\"");
        var temperatures = Enumerable.Range(0, 48)
            .Select(i => (5.0 + i * 0.5).ToString(System.Globalization.CultureInfo.InvariantCulture));

        var jsonResponse = $$"""
            {
                "hourly": {
                    "time": [{{string.Join(", ", times)}}],
                    "temperature_2m": [{{string.Join(", ", temperatures)}}]
                }
            }
            """;
        _mockHttp
            .When(OpenMeteoApiUrl)
            .Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.GetForecastAsync(TestLatitude, TestLongitude, forecastHours: 48);

        // Then
        result!.HourlyPoints.Should().HaveCount(48);
    }

    #endregion

    #region Given decimal precision in temperatures

    [Theory]
    [InlineData(5.123456789, 5.123456789)]
    [InlineData(-0.1, -0.1)]
    [InlineData(0.0, 0.0)]
    [InlineData(99.9, 99.9)]
    [InlineData(-40.0, -40.0)]
    public async Task GetForecastAsync_GivenVariousTemperatureValues_WhenCalled_ThenMapsWithCorrectPrecision(
        double inputTemperature, decimal expectedTemperature)
    {
        // Given
        var jsonResponse = $$"""
            {
                "hourly": {
                    "time": ["2024-01-15T10:00"],
                    "temperature_2m": [{{inputTemperature.ToString(System.Globalization.CultureInfo.InvariantCulture)}}]
                }
            }
            """;
        _mockHttp
            .When(OpenMeteoApiUrl)
            .Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.GetForecastAsync(TestLatitude, TestLongitude);

        // Then
        result!.HourlyPoints[0].TemperatureCelsius.Should().Be(expectedTemperature);
    }

    #endregion

    #region Given various coordinate values

    [Theory]
    [InlineData(0.0, 0.0)]         // Equator/Prime Meridian
    [InlineData(90.0, 0.0)]        // North Pole
    [InlineData(-90.0, 0.0)]       // South Pole
    [InlineData(0.0, 180.0)]       // Date Line
    [InlineData(0.0, -180.0)]      // Date Line (negative)
    [InlineData(51.5074, -0.1278)] // London
    [InlineData(-33.8688, 151.2093)] // Sydney
    public async Task GetForecastAsync_GivenVariousCoordinates_WhenCalled_ThenMakesValidRequest(
        double latitude, double longitude)
    {
        // Given
        var jsonResponse = CreateValidJsonResponse();
        _mockHttp
            .When(OpenMeteoApiUrl)
            .Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.GetForecastAsync(latitude, longitude);

        // Then
        result.Should().NotBeNull();
    }

    #endregion

    #region Given logging behavior

    [Fact]
    public async Task GetForecastAsync_GivenSuccessfulFetch_WhenCalled_ThenLogsInformation()
    {
        // Given
        var jsonResponse = CreateValidJsonResponse();
        _mockHttp
            .When(OpenMeteoApiUrl)
            .Respond(ApplicationJson, jsonResponse);

        // When
        await _sut.GetForecastAsync(TestLatitude, TestLongitude);

        // Then
        _logger.Received().Log(
            LogLevel.Information,
            Arg.Any<EventId>(),
            Arg.Is<object>(o => o.ToString()!.Contains("Fetched") && o.ToString()!.Contains("forecast points")),
            Arg.Any<Exception?>(),
            Arg.Any<Func<object, Exception?, string>>());
    }

    [Fact]
    public async Task GetForecastAsync_GivenHttpError_WhenCalled_ThenLogsWarning()
    {
        // Given
        _mockHttp
            .When(OpenMeteoApiUrl)
            .Respond(HttpStatusCode.InternalServerError);

        // When
        await _sut.GetForecastAsync(TestLatitude, TestLongitude);

        // Then
        _logger.Received().Log(
            LogLevel.Warning,
            Arg.Any<EventId>(),
            Arg.Any<object>(),
            Arg.Any<Exception?>(),
            Arg.Any<Func<object, Exception?, string>>());
    }

    #endregion

    #region Given complete forecast scenario

    [Fact]
    public async Task GetForecastAsync_GivenRealisticApiResponse_WhenCalled_ThenReturnsFullyMappedForecast()
    {
        // Given - realistic Open-Meteo response
        var jsonResponse = """
            {
                "latitude": 52.23,
                "longitude": 21.01,
                "generationtime_ms": 0.123,
                "utc_offset_seconds": 3600,
                "timezone": "Europe/Warsaw",
                "timezone_abbreviation": "CET",
                "elevation": 105.0,
                "hourly_units": {
                    "time": "iso8601",
                    "temperature_2m": "°C"
                },
                "hourly": {
                    "time": [
                        "2024-01-15T00:00",
                        "2024-01-15T01:00",
                        "2024-01-15T02:00",
                        "2024-01-15T03:00",
                        "2024-01-15T04:00",
                        "2024-01-15T05:00"
                    ],
                    "temperature_2m": [-2.1, -2.5, -3.0, -3.2, -3.5, -3.1]
                }
            }
            """;
        _mockHttp
            .When(OpenMeteoApiUrl)
            .Respond(ApplicationJson, jsonResponse);

        // When
        var result = await _sut.GetForecastAsync(TestLatitude, TestLongitude, forecastHours: 6);

        // Then
        result.Should().NotBeNull();
        result!.HourlyPoints.Should().HaveCount(6);
        result.HourlyPoints.Should().AllSatisfy(p =>
        {
            p.TemperatureCelsius.Should().BeLessThan(0);
            p.ForecastTimestamp.Year.Should().Be(2024);
        });
        result.FetchedAt.Should().BeCloseTo(DateTimeOffset.UtcNow, TimeSpan.FromSeconds(5));
    }

    #endregion

    #region Helper methods

    private static string CreateValidJsonResponse() => """
        {
            "hourly": {
                "time": ["2024-01-15T10:00", "2024-01-15T11:00", "2024-01-15T12:00"],
                "temperature_2m": [5.2, 6.8, 7.1]
            }
        }
        """;

    #endregion
}
