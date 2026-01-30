using FluentAssertions;
using PumpAhead.Adapters.Out.Persistence.SqlServer.Entities;
using PumpAhead.Adapters.Out.Persistence.SqlServer.Repositories;
using PumpAhead.Tests.Common.Fixtures;
using PumpAhead.UseCases.Ports.Out;

namespace PumpAhead.Adapters.Out.Tests.Repositories;

public class SqlServerWeatherForecastRepositoryTests : IntegrationTestBase
{
    private const int DefaultForecastHours = 12;
    private const int ShortForecastHours = 6;
    private const decimal Temperature10 = 10.0m;
    private const decimal Temperature105 = 10.5m;
    private const decimal Temperature11 = 11.0m;
    private const decimal Temperature115 = 11.5m;
    private const decimal Temperature12 = 12.0m;
    private const decimal Temperature15 = 15.0m;
    private const decimal Temperature8 = 8.0m;
    private const decimal Temperature16 = 16.0m;
    private const decimal Temperature20 = 20.0m;
    private const decimal Temperature5 = 5.0m;

    private static readonly DateTimeOffset BaseTestTime = new(2024, 6, 15, 12, 0, 0, TimeSpan.Zero);

    #region SaveForecastAsync

    [Fact]
    public async Task SaveForecastAsync_GivenValidForecastPoints_WhenSaved_ThenPersistsToDatabase()
    {
        // Given
        await using var context = CreateContext();
        var repository = new SqlServerWeatherForecastRepository(context);
        var fetchedAt = DateTimeOffset.UtcNow;
        var points = new List<WeatherForecastPoint>
        {
            new(10.5m, fetchedAt.AddHours(1)),
            new(12.0m, fetchedAt.AddHours(2)),
            new(11.5m, fetchedAt.AddHours(3))
        };

        // When
        await repository.SaveForecastAsync(points, fetchedAt);

        // Then
        await using var verifyContext = CreateContext();
        var savedEntities = verifyContext.WeatherForecasts.ToList();
        savedEntities.Should().HaveCount(3);
    }

    [Fact]
    public async Task SaveForecastAsync_GivenValidForecastPoints_WhenSaved_ThenStoresCorrectTemperatures()
    {
        // Given
        await using var context = CreateContext();
        var repository = new SqlServerWeatherForecastRepository(context);
        var fetchedAt = DateTimeOffset.UtcNow;
        var points = new List<WeatherForecastPoint>
        {
            new(Temperature105, fetchedAt.AddHours(1)),
            new(Temperature12, fetchedAt.AddHours(2))
        };

        // When
        await repository.SaveForecastAsync(points, fetchedAt);

        // Then
        await using var verifyContext = CreateContext();
        var savedEntities = verifyContext.WeatherForecasts.OrderBy(e => e.ForecastTimestamp).ToList();
        savedEntities[0].TemperatureCelsius.Should().Be(Temperature105);
        savedEntities[1].TemperatureCelsius.Should().Be(Temperature12);
    }

    [Fact]
    public async Task SaveForecastAsync_GivenValidForecastPoints_WhenSaved_ThenStoresCorrectTimestamps()
    {
        // Given
        await using var context = CreateContext();
        var repository = new SqlServerWeatherForecastRepository(context);
        var fetchedAt = BaseTestTime;
        var forecastTime1 = fetchedAt.AddHours(1);
        var forecastTime2 = fetchedAt.AddHours(2);
        var points = new List<WeatherForecastPoint>
        {
            new(Temperature105, forecastTime1),
            new(Temperature12, forecastTime2)
        };

        // When
        await repository.SaveForecastAsync(points, fetchedAt);

        // Then
        await using var verifyContext = CreateContext();
        var savedEntities = verifyContext.WeatherForecasts.OrderBy(e => e.ForecastTimestamp).ToList();
        savedEntities[0].ForecastTimestamp.Should().Be(forecastTime1);
        savedEntities[1].ForecastTimestamp.Should().Be(forecastTime2);
    }

    [Fact]
    public async Task SaveForecastAsync_GivenValidForecastPoints_WhenSaved_ThenStoresCorrectFetchedAt()
    {
        // Given
        await using var context = CreateContext();
        var repository = new SqlServerWeatherForecastRepository(context);
        var fetchedAt = BaseTestTime;
        var points = new List<WeatherForecastPoint>
        {
            new(Temperature105, fetchedAt.AddHours(1)),
            new(Temperature12, fetchedAt.AddHours(2))
        };

        // When
        await repository.SaveForecastAsync(points, fetchedAt);

        // Then
        await using var verifyContext = CreateContext();
        var savedEntities = verifyContext.WeatherForecasts.ToList();
        savedEntities.Should().AllSatisfy(e => e.FetchedAt.Should().Be(fetchedAt));
    }

    [Fact]
    public async Task SaveForecastAsync_GivenEmptyForecastPoints_WhenSaved_ThenNothingIsPersisted()
    {
        // Given
        await using var context = CreateContext();
        var repository = new SqlServerWeatherForecastRepository(context);
        var fetchedAt = DateTimeOffset.UtcNow;
        var points = new List<WeatherForecastPoint>();

        // When
        await repository.SaveForecastAsync(points, fetchedAt);

        // Then
        await using var verifyContext = CreateContext();
        var savedEntities = verifyContext.WeatherForecasts.ToList();
        savedEntities.Should().BeEmpty();
    }

    #endregion

    #region GetForecastFromAsync - Basic Retrieval

    [Fact]
    public async Task GetForecastFromAsync_GivenExistingForecasts_WhenQueried_ThenReturnsForecastsInTimeRange()
    {
        // Given
        var baseTime = BaseTestTime;
        var fetchedAt = baseTime;
        Given(ctx =>
        {
            ctx.WeatherForecasts.AddRange(
                new WeatherForecastEntity { TemperatureCelsius = Temperature10, ForecastTimestamp = baseTime.AddHours(1), FetchedAt = fetchedAt },
                new WeatherForecastEntity { TemperatureCelsius = Temperature11, ForecastTimestamp = baseTime.AddHours(2), FetchedAt = fetchedAt },
                new WeatherForecastEntity { TemperatureCelsius = Temperature12, ForecastTimestamp = baseTime.AddHours(3), FetchedAt = fetchedAt }
            );
        });

        await using var context = CreateContext();
        var repository = new SqlServerWeatherForecastRepository(context);

        // When
        var result = await repository.GetForecastFromAsync(baseTime, hours: DefaultForecastHours);

        // Then
        result.Should().HaveCount(3);
    }

    [Fact]
    public async Task GetForecastFromAsync_GivenExistingForecasts_WhenQueried_ThenReturnsCorrectTemperatures()
    {
        // Given
        var baseTime = BaseTestTime;
        var fetchedAt = baseTime;
        Given(ctx =>
        {
            ctx.WeatherForecasts.AddRange(
                new WeatherForecastEntity { TemperatureCelsius = Temperature105, ForecastTimestamp = baseTime.AddHours(1), FetchedAt = fetchedAt },
                new WeatherForecastEntity { TemperatureCelsius = Temperature12, ForecastTimestamp = baseTime.AddHours(2), FetchedAt = fetchedAt }
            );
        });

        await using var context = CreateContext();
        var repository = new SqlServerWeatherForecastRepository(context);

        // When
        var result = await repository.GetForecastFromAsync(baseTime, hours: DefaultForecastHours);

        // Then
        result.Should().ContainSingle(p => p.TemperatureCelsius == Temperature105);
        result.Should().ContainSingle(p => p.TemperatureCelsius == Temperature12);
    }

    [Fact]
    public async Task GetForecastFromAsync_GivenExistingForecasts_WhenQueried_ThenReturnsOrderedByTimestamp()
    {
        // Given
        var baseTime = BaseTestTime;
        var fetchedAt = baseTime;
        Given(ctx =>
        {
            // Add in non-chronological order
            ctx.WeatherForecasts.AddRange(
                new WeatherForecastEntity { TemperatureCelsius = Temperature12, ForecastTimestamp = baseTime.AddHours(3), FetchedAt = fetchedAt },
                new WeatherForecastEntity { TemperatureCelsius = Temperature10, ForecastTimestamp = baseTime.AddHours(1), FetchedAt = fetchedAt },
                new WeatherForecastEntity { TemperatureCelsius = Temperature11, ForecastTimestamp = baseTime.AddHours(2), FetchedAt = fetchedAt }
            );
        });

        await using var context = CreateContext();
        var repository = new SqlServerWeatherForecastRepository(context);

        // When
        var result = await repository.GetForecastFromAsync(baseTime, hours: DefaultForecastHours);

        // Then
        result.Should().BeInAscendingOrder(p => p.ForecastTimestamp);
        result[0].TemperatureCelsius.Should().Be(Temperature10);
        result[1].TemperatureCelsius.Should().Be(Temperature11);
        result[2].TemperatureCelsius.Should().Be(Temperature12);
    }

    #endregion

    #region GetForecastFromAsync - Date Filtering

    [Fact]
    public async Task GetForecastFromAsync_GivenForecastsOutsideRange_WhenQueried_ThenExcludesForecastsBeforeFromDate()
    {
        // Given
        var baseTime = BaseTestTime;
        var fetchedAt = baseTime;
        Given(ctx =>
        {
            ctx.WeatherForecasts.AddRange(
                // Before range
                new WeatherForecastEntity { TemperatureCelsius = Temperature8, ForecastTimestamp = baseTime.AddHours(-1), FetchedAt = fetchedAt },
                // Inside range
                new WeatherForecastEntity { TemperatureCelsius = Temperature10, ForecastTimestamp = baseTime.AddHours(1), FetchedAt = fetchedAt },
                new WeatherForecastEntity { TemperatureCelsius = Temperature11, ForecastTimestamp = baseTime.AddHours(2), FetchedAt = fetchedAt }
            );
        });

        await using var context = CreateContext();
        var repository = new SqlServerWeatherForecastRepository(context);

        // When
        var result = await repository.GetForecastFromAsync(baseTime, hours: DefaultForecastHours);

        // Then
        result.Should().HaveCount(2);
        result.Should().NotContain(p => p.TemperatureCelsius == Temperature8);
    }

    [Fact]
    public async Task GetForecastFromAsync_GivenForecastsOutsideRange_WhenQueried_ThenExcludesForecastsAfterToDate()
    {
        // Given
        var baseTime = BaseTestTime;
        var fetchedAt = baseTime;
        Given(ctx =>
        {
            ctx.WeatherForecasts.AddRange(
                // Inside range (12 hours = up to baseTime + 12 hours)
                new WeatherForecastEntity { TemperatureCelsius = Temperature10, ForecastTimestamp = baseTime.AddHours(1), FetchedAt = fetchedAt },
                new WeatherForecastEntity { TemperatureCelsius = Temperature11, ForecastTimestamp = baseTime.AddHours(11), FetchedAt = fetchedAt },
                // Outside range
                new WeatherForecastEntity { TemperatureCelsius = Temperature15, ForecastTimestamp = baseTime.AddHours(13), FetchedAt = fetchedAt }
            );
        });

        await using var context = CreateContext();
        var repository = new SqlServerWeatherForecastRepository(context);

        // When
        var result = await repository.GetForecastFromAsync(baseTime, hours: DefaultForecastHours);

        // Then
        result.Should().HaveCount(2);
        result.Should().NotContain(p => p.TemperatureCelsius == Temperature15);
    }

    [Fact]
    public async Task GetForecastFromAsync_GivenCustomHoursParameter_WhenQueried_ThenRespectsTimeRange()
    {
        // Given
        var baseTime = BaseTestTime;
        var fetchedAt = baseTime;
        Given(ctx =>
        {
            ctx.WeatherForecasts.AddRange(
                new WeatherForecastEntity { TemperatureCelsius = Temperature10, ForecastTimestamp = baseTime.AddHours(1), FetchedAt = fetchedAt },
                new WeatherForecastEntity { TemperatureCelsius = Temperature11, ForecastTimestamp = baseTime.AddHours(5), FetchedAt = fetchedAt },
                new WeatherForecastEntity { TemperatureCelsius = Temperature12, ForecastTimestamp = baseTime.AddHours(7), FetchedAt = fetchedAt }
            );
        });

        await using var context = CreateContext();
        var repository = new SqlServerWeatherForecastRepository(context);

        // When - only 6 hours range
        var result = await repository.GetForecastFromAsync(baseTime, hours: ShortForecastHours);

        // Then
        result.Should().HaveCount(2);
        result.Should().NotContain(p => p.TemperatureCelsius == Temperature12);
    }

    [Fact]
    public async Task GetForecastFromAsync_GivenForecastAtExactFromTime_WhenQueried_ThenIncludesIt()
    {
        // Given
        var baseTime = BaseTestTime;
        var fetchedAt = baseTime;
        Given(ctx =>
        {
            ctx.WeatherForecasts.Add(
                new WeatherForecastEntity { TemperatureCelsius = Temperature10, ForecastTimestamp = baseTime, FetchedAt = fetchedAt }
            );
        });

        await using var context = CreateContext();
        var repository = new SqlServerWeatherForecastRepository(context);

        // When
        var result = await repository.GetForecastFromAsync(baseTime, hours: DefaultForecastHours);

        // Then
        result.Should().HaveCount(1);
        result[0].TemperatureCelsius.Should().Be(Temperature10);
    }

    [Fact]
    public async Task GetForecastFromAsync_GivenForecastAtExactToTime_WhenQueried_ThenIncludesIt()
    {
        // Given
        var baseTime = BaseTestTime;
        var fetchedAt = baseTime;
        Given(ctx =>
        {
            ctx.WeatherForecasts.Add(
                new WeatherForecastEntity { TemperatureCelsius = Temperature10, ForecastTimestamp = baseTime.AddHours(DefaultForecastHours), FetchedAt = fetchedAt }
            );
        });

        await using var context = CreateContext();
        var repository = new SqlServerWeatherForecastRepository(context);

        // When
        var result = await repository.GetForecastFromAsync(baseTime, hours: DefaultForecastHours);

        // Then
        result.Should().HaveCount(1);
        result[0].TemperatureCelsius.Should().Be(Temperature10);
    }

    #endregion

    #region GetForecastFromAsync - Empty Results

    [Fact]
    public async Task GetForecastFromAsync_GivenNoForecastsInDatabase_WhenQueried_ThenReturnsEmptyCollection()
    {
        // Given
        var baseTime = BaseTestTime;
        await using var context = CreateContext();
        var repository = new SqlServerWeatherForecastRepository(context);

        // When
        var result = await repository.GetForecastFromAsync(baseTime, hours: DefaultForecastHours);

        // Then
        result.Should().BeEmpty();
    }

    [Fact]
    public async Task GetForecastFromAsync_GivenForecastsOnlyOutsideRange_WhenQueried_ThenReturnsEmptyCollection()
    {
        // Given
        var baseTime = BaseTestTime;
        var fetchedAt = baseTime;
        Given(ctx =>
        {
            ctx.WeatherForecasts.AddRange(
                new WeatherForecastEntity { TemperatureCelsius = Temperature5, ForecastTimestamp = baseTime.AddHours(-5), FetchedAt = fetchedAt },
                new WeatherForecastEntity { TemperatureCelsius = Temperature20, ForecastTimestamp = baseTime.AddHours(20), FetchedAt = fetchedAt }
            );
        });

        await using var context = CreateContext();
        var repository = new SqlServerWeatherForecastRepository(context);

        // When
        var result = await repository.GetForecastFromAsync(baseTime, hours: DefaultForecastHours);

        // Then
        result.Should().BeEmpty();
    }

    #endregion

    #region GetForecastFromAsync - Multiple Fetches (Latest Fetch Selection)

    [Fact]
    public async Task GetForecastFromAsync_GivenMultipleFetches_WhenQueried_ThenReturnsOnlyLatestFetch()
    {
        // Given
        var baseTime = BaseTestTime;
        var olderFetch = baseTime.AddHours(-2);
        var newerFetch = baseTime.AddHours(-1);

        Given(ctx =>
        {
            // Older fetch
            ctx.WeatherForecasts.AddRange(
                new WeatherForecastEntity { TemperatureCelsius = Temperature10, ForecastTimestamp = baseTime.AddHours(1), FetchedAt = olderFetch },
                new WeatherForecastEntity { TemperatureCelsius = Temperature11, ForecastTimestamp = baseTime.AddHours(2), FetchedAt = olderFetch }
            );
            // Newer fetch (should be returned)
            ctx.WeatherForecasts.AddRange(
                new WeatherForecastEntity { TemperatureCelsius = Temperature15, ForecastTimestamp = baseTime.AddHours(1), FetchedAt = newerFetch },
                new WeatherForecastEntity { TemperatureCelsius = Temperature16, ForecastTimestamp = baseTime.AddHours(2), FetchedAt = newerFetch }
            );
        });

        await using var context = CreateContext();
        var repository = new SqlServerWeatherForecastRepository(context);

        // When
        var result = await repository.GetForecastFromAsync(baseTime, hours: DefaultForecastHours);

        // Then
        result.Should().HaveCount(2);
        result.Should().AllSatisfy(p => p.TemperatureCelsius.Should().BeGreaterThanOrEqualTo(Temperature15));
    }

    [Fact]
    public async Task GetForecastFromAsync_GivenMultipleFetches_WhenQueried_ThenDoesNotMixFetchData()
    {
        // Given
        var baseTime = BaseTestTime;
        var olderFetch = baseTime.AddHours(-2);
        var newerFetch = baseTime.AddHours(-1);

        Given(ctx =>
        {
            // Older fetch with temperature 10
            ctx.WeatherForecasts.Add(
                new WeatherForecastEntity { TemperatureCelsius = Temperature10, ForecastTimestamp = baseTime.AddHours(1), FetchedAt = olderFetch }
            );
            // Newer fetch with temperature 20
            ctx.WeatherForecasts.Add(
                new WeatherForecastEntity { TemperatureCelsius = Temperature20, ForecastTimestamp = baseTime.AddHours(2), FetchedAt = newerFetch }
            );
        });

        await using var context = CreateContext();
        var repository = new SqlServerWeatherForecastRepository(context);

        // When
        var result = await repository.GetForecastFromAsync(baseTime, hours: DefaultForecastHours);

        // Then - should only get the newer fetch data
        result.Should().HaveCount(1);
        result[0].TemperatureCelsius.Should().Be(Temperature20);
    }

    #endregion

    #region SaveForecastAsync + GetForecastFromAsync Integration

    [Fact]
    public async Task SaveAndGet_GivenSavedForecasts_WhenRetrieved_ThenReturnsCorrectData()
    {
        // Given
        var fetchedAt = BaseTestTime;
        var points = new List<WeatherForecastPoint>
        {
            new(Temperature105, fetchedAt.AddHours(1)),
            new(Temperature12, fetchedAt.AddHours(2)),
            new(Temperature115, fetchedAt.AddHours(3))
        };

        await using var saveContext = CreateContext();
        var saveRepository = new SqlServerWeatherForecastRepository(saveContext);
        await saveRepository.SaveForecastAsync(points, fetchedAt);

        // When
        await using var getContext = CreateContext();
        var getRepository = new SqlServerWeatherForecastRepository(getContext);
        var result = await getRepository.GetForecastFromAsync(fetchedAt, hours: DefaultForecastHours);

        // Then
        result.Should().HaveCount(3);
        result.Select(p => p.TemperatureCelsius).Should().BeEquivalentTo(new[] { Temperature105, Temperature12, Temperature115 });
    }

    #endregion
}
