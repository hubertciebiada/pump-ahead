using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using PumpAhead.Adapters.Out.Persistence.SqlServer.Entities;

namespace PumpAhead.Adapters.Out.Persistence.SqlServer.Configuration;

public class HeatPumpConfiguration : IEntityTypeConfiguration<HeatPumpEntity>
{
    public void Configure(EntityTypeBuilder<HeatPumpEntity> builder)
    {
        builder.ToTable("HeatPumps");

        builder.HasKey(hp => hp.Id);

        builder.Property(hp => hp.Model)
            .HasMaxLength(100)
            .IsRequired();

        builder.Property(hp => hp.LastSyncTime)
            .IsRequired();

        builder.Property(hp => hp.OperatingMode)
            .IsRequired();

        builder.Property(hp => hp.CH_FlowTemperature)
            .HasPrecision(5, 2)
            .IsRequired();

        builder.Property(hp => hp.CH_ReturnTemperature)
            .HasPrecision(5, 2)
            .IsRequired();

        builder.Property(hp => hp.CH_Offset)
            .HasPrecision(4, 2)
            .IsRequired();

        builder.Property(hp => hp.DHW_ActualTemperature)
            .HasPrecision(5, 2)
            .IsRequired();

        builder.Property(hp => hp.DHW_TargetTemperature)
            .HasPrecision(5, 2)
            .IsRequired();

        builder.Property(hp => hp.DHW_Delta)
            .HasPrecision(4, 2)
            .IsRequired();

        builder.Property(hp => hp.Compressor_Frequency)
            .HasPrecision(6, 2)
            .IsRequired();

        builder.HasIndex(hp => hp.LastSyncTime)
            .IsDescending();
    }
}
