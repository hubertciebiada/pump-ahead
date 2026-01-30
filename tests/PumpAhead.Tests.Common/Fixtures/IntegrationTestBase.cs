using PumpAhead.Adapters.Out.Persistence.SqlServer;

namespace PumpAhead.Tests.Common.Fixtures;

/// <summary>
/// Base class for integration tests that need database access.
/// Provides automatic setup and cleanup of the in-memory database.
///
/// Usage (AAA pattern compatible with Given-When-Then):
///
/// public class MyIntegrationTests : IntegrationTestBase
/// {
///     [Fact]
///     public async Task Should_do_something()
///     {
///         // Given (Arrange)
///         await GivenAsync(ctx => {
///             ctx.HeatPumps.Add(...);
///         });
///
///         // When (Act)
///         await using var context = CreateContext();
///         var result = await someRepository.GetAsync(...);
///
///         // Then (Assert)
///         result.Should().NotBeNull();
///     }
/// }
/// </summary>
public abstract class IntegrationTestBase : IDisposable
{
    private readonly TestDbContextFactory _factory;
    private bool _disposed;

    protected IntegrationTestBase()
    {
        _factory = new TestDbContextFactory();
    }

    /// <summary>
    /// Creates a new DbContext instance.
    /// </summary>
    protected PumpAheadDbContext CreateContext() => _factory.CreateContext();

    /// <summary>
    /// Creates a new DbContext with the database ensured to be created.
    /// </summary>
    protected PumpAheadDbContext CreateContextAndEnsureCreated() => _factory.CreateContextAndEnsureCreated();

    /// <summary>
    /// Sets up the test data (Given / Arrange phase).
    /// </summary>
    protected void Given(Action<PumpAheadDbContext> setup)
    {
        _factory.Seed(setup);
    }

    /// <summary>
    /// Sets up the test data asynchronously (Given / Arrange phase).
    /// </summary>
    protected async Task GivenAsync(Func<PumpAheadDbContext, Task> setup)
    {
        await _factory.SeedAsync(setup);
    }

    /// <summary>
    /// Resets the database to a clean state.
    /// </summary>
    protected void ResetDatabase()
    {
        _factory.Reset();
    }

    /// <summary>
    /// Gets the underlying factory for advanced scenarios.
    /// </summary>
    protected TestDbContextFactory Factory => _factory;

    public void Dispose()
    {
        Dispose(true);
        GC.SuppressFinalize(this);
    }

    protected virtual void Dispose(bool disposing)
    {
        if (!_disposed && disposing)
        {
            _factory.Dispose();
            _disposed = true;
        }
    }
}
