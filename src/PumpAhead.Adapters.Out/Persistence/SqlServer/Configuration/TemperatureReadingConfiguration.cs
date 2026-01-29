using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using PumpAhead.Adapters.Out.Persistence.SqlServer.Entities;

namespace PumpAhead.Adapters.Out.Persistence.SqlServer.Configuration;

public class TemperatureReadingConfiguration : IEntityTypeConfiguration<TemperatureReadingEntity>
{
    public void Configure(EntityTypeBuilder<TemperatureReadingEntity> builder)
    {
        builder.ToTable("TemperatureReadings");

        builder.HasKey(r => r.Id);

        builder.Property(r => r.SensorId)
            .HasMaxLength(255)
            .IsRequired();

        builder.Property(r => r.Temperature)
            .HasPrecision(5, 2);

        builder.HasIndex(r => new { r.SensorId, r.Timestamp })
            .IsDescending(false, true);
    }
}
