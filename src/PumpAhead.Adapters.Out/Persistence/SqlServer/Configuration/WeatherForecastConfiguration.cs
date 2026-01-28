using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using PumpAhead.Adapters.Out.Persistence.SqlServer.Entities;

namespace PumpAhead.Adapters.Out.Persistence.SqlServer.Configuration;

public class WeatherForecastConfiguration : IEntityTypeConfiguration<WeatherForecastEntity>
{
    public void Configure(EntityTypeBuilder<WeatherForecastEntity> builder)
    {
        builder.ToTable("WeatherForecasts");

        builder.HasKey(e => e.Id);

        builder.Property(e => e.TemperatureCelsius)
            .HasPrecision(5, 2)
            .IsRequired();

        builder.Property(e => e.ForecastTimestamp)
            .IsRequired();

        builder.Property(e => e.FetchedAt)
            .IsRequired();

        builder.HasIndex(e => e.ForecastTimestamp);
        builder.HasIndex(e => e.FetchedAt);
    }
}
