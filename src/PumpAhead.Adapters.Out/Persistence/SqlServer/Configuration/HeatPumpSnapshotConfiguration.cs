using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using PumpAhead.Adapters.Out.Persistence.SqlServer.Entities;

namespace PumpAhead.Adapters.Out.Persistence.SqlServer.Configuration;

public class HeatPumpSnapshotConfiguration : IEntityTypeConfiguration<HeatPumpSnapshotEntity>
{
    public void Configure(EntityTypeBuilder<HeatPumpSnapshotEntity> builder)
    {
        builder.ToTable("HeatPumpSnapshots");

        builder.HasKey(s => s.Id);

        builder.Property(s => s.PumpFlow)
            .HasPrecision(6, 2);

        builder.Property(s => s.OutsideTemperature)
            .HasPrecision(5, 2);

        builder.Property(s => s.CH_InletTemperature)
            .HasPrecision(5, 2);

        builder.Property(s => s.CH_OutletTemperature)
            .HasPrecision(5, 2);

        builder.Property(s => s.CH_TargetTemperature)
            .HasPrecision(5, 2);

        builder.Property(s => s.DHW_ActualTemperature)
            .HasPrecision(5, 2);

        builder.Property(s => s.DHW_TargetTemperature)
            .HasPrecision(5, 2);

        builder.Property(s => s.Compressor_Frequency)
            .HasPrecision(6, 2);

        // Power data
        builder.Property(s => s.Power_HeatProduction)
            .HasPrecision(7, 2);

        builder.Property(s => s.Power_HeatConsumption)
            .HasPrecision(7, 2);

        builder.Property(s => s.Power_CoolProduction)
            .HasPrecision(7, 2);

        builder.Property(s => s.Power_CoolConsumption)
            .HasPrecision(7, 2);

        builder.Property(s => s.Power_DhwProduction)
            .HasPrecision(7, 2);

        builder.Property(s => s.Power_DhwConsumption)
            .HasPrecision(7, 2);

        // Operations data
        builder.Property(s => s.Operations_CompressorHours)
            .HasPrecision(8, 2);

        // Error code
        builder.Property(s => s.ErrorCode)
            .HasMaxLength(20);

        // Composite index for efficient range queries by HeatPumpId and Timestamp
        builder.HasIndex(s => new { s.HeatPumpId, s.Timestamp })
            .IsDescending(false, true);
    }
}
