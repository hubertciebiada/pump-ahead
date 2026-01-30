using Microsoft.EntityFrameworkCore;
using PumpAhead.Adapters.Out.Persistence.SqlServer;

namespace PumpAhead.Tests.Common.Fixtures;

/// <summary>
/// Factory for creating in-memory DbContext instances for integration tests.
/// Each test gets an isolated database instance.
/// </summary>
public sealed class TestDbContextFactory : IDisposable
{
    private readonly string _databaseName;
    private readonly DbContextOptions<PumpAheadDbContext> _options;
    private bool _disposed;

    /// <summary>
    /// Creates a new factory with a unique database name.
    /// </summary>
    public TestDbContextFactory() : this(Guid.NewGuid().ToString())
    {
    }

    /// <summary>
    /// Creates a new factory with a specific database name.
    /// Useful when you need to share the database between multiple contexts.
    /// </summary>
    public TestDbContextFactory(string databaseName)
    {
        _databaseName = databaseName;
        _options = new DbContextOptionsBuilder<PumpAheadDbContext>()
            .UseInMemoryDatabase(_databaseName)
            .EnableSensitiveDataLogging()
            .EnableDetailedErrors()
            .Options;
    }

    /// <summary>
    /// Creates a new DbContext instance.
    /// Multiple calls return different instances sharing the same in-memory database.
    /// </summary>
    public PumpAheadDbContext CreateContext()
    {
        ObjectDisposedException.ThrowIf(_disposed, this);
        return new PumpAheadDbContext(_options);
    }

    /// <summary>
    /// Creates a new DbContext and ensures the database is created.
    /// </summary>
    public PumpAheadDbContext CreateContextAndEnsureCreated()
    {
        var context = CreateContext();
        context.Database.EnsureCreated();
        return context;
    }

    /// <summary>
    /// Seeds the database with data using a setup action.
    /// </summary>
    public void Seed(Action<PumpAheadDbContext> seedAction)
    {
        using var context = CreateContext();
        seedAction(context);
        context.SaveChanges();
    }

    /// <summary>
    /// Seeds the database with data using an async setup action.
    /// </summary>
    public async Task SeedAsync(Func<PumpAheadDbContext, Task> seedAction)
    {
        await using var context = CreateContext();
        await seedAction(context);
        await context.SaveChangesAsync();
    }

    /// <summary>
    /// Resets the database by deleting and recreating it.
    /// </summary>
    public void Reset()
    {
        using var context = CreateContext();
        context.Database.EnsureDeleted();
        context.Database.EnsureCreated();
    }

    /// <summary>
    /// Gets the database options for advanced scenarios.
    /// </summary>
    public DbContextOptions<PumpAheadDbContext> Options => _options;

    public void Dispose()
    {
        if (!_disposed)
        {
            // Clean up the in-memory database
            using var context = new PumpAheadDbContext(_options);
            context.Database.EnsureDeleted();
            _disposed = true;
        }
    }
}

/// <summary>
/// Extension methods for TestDbContextFactory to support fluent test setup.
/// </summary>
public static class TestDbContextFactoryExtensions
{
    /// <summary>
    /// Seeds the database and returns the factory for method chaining.
    /// </summary>
    public static TestDbContextFactory WithSeed(
        this TestDbContextFactory factory,
        Action<PumpAheadDbContext> seedAction)
    {
        factory.Seed(seedAction);
        return factory;
    }

    /// <summary>
    /// Seeds multiple entities of the same type.
    /// </summary>
    public static TestDbContextFactory WithEntities<T>(
        this TestDbContextFactory factory,
        params T[] entities) where T : class
    {
        factory.Seed(ctx => ctx.Set<T>().AddRange(entities));
        return factory;
    }
}
