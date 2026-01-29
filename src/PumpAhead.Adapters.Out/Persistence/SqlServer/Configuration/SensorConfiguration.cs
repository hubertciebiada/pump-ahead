using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using PumpAhead.Adapters.Out.Persistence.SqlServer.Entities;

namespace PumpAhead.Adapters.Out.Persistence.SqlServer.Configuration;

public class SensorConfiguration : IEntityTypeConfiguration<SensorEntity>
{
    public void Configure(EntityTypeBuilder<SensorEntity> builder)
    {
        builder.ToTable("Sensors");

        builder.HasKey(s => s.Id);

        builder.Property(s => s.Name)
            .HasMaxLength(100)
            .IsRequired();

        builder.Property(s => s.Label)
            .HasMaxLength(100);

        builder.Property(s => s.Address)
            .HasMaxLength(255)
            .IsRequired();

        builder.Property(s => s.Type)
            .HasMaxLength(50)
            .IsRequired();

        builder.HasMany(s => s.Readings)
            .WithOne()
            .HasForeignKey(r => r.SensorId)
            .OnDelete(DeleteBehavior.Cascade);
    }
}
