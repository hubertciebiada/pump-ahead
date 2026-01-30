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

        builder.Property(hp => hp.PumpFlow)
            .HasPrecision(6, 2);

        builder.Property(hp => hp.OutsideTemperature)
            .HasPrecision(5, 2);

        builder.Property(hp => hp.CH_InletTemperature)
            .HasPrecision(5, 2);

        builder.Property(hp => hp.CH_OutletTemperature)
            .HasPrecision(5, 2);

        builder.Property(hp => hp.CH_TargetTemperature)
            .HasPrecision(5, 2);

        builder.Property(hp => hp.DHW_ActualTemperature)
            .HasPrecision(5, 2);

        builder.Property(hp => hp.DHW_TargetTemperature)
            .HasPrecision(5, 2);

        builder.Property(hp => hp.Compressor_Frequency)
            .HasPrecision(6, 2);

        // Power data (watts - up to 99999.99)
        builder.Property(hp => hp.Power_HeatProduction)
            .HasPrecision(7, 2);

        builder.Property(hp => hp.Power_HeatConsumption)
            .HasPrecision(7, 2);

        builder.Property(hp => hp.Power_CoolProduction)
            .HasPrecision(7, 2);

        builder.Property(hp => hp.Power_CoolConsumption)
            .HasPrecision(7, 2);

        builder.Property(hp => hp.Power_DhwProduction)
            .HasPrecision(7, 2);

        builder.Property(hp => hp.Power_DhwConsumption)
            .HasPrecision(7, 2);

        // Operations data (hours - up to 999999.99)
        builder.Property(hp => hp.Operations_CompressorHours)
            .HasPrecision(8, 2);

        // Error code
        builder.Property(hp => hp.ErrorCode)
            .HasMaxLength(20);

        builder.HasIndex(hp => hp.LastSyncTime)
            .IsDescending();
    }
}
