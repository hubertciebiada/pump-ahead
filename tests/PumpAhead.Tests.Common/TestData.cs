using PumpAhead.DeepModel;
using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.Tests.Common;

/// <summary>
/// Static factory methods for creating common test data scenarios.
/// Provides well-known test data for consistent, readable tests.
/// </summary>
public static class TestData
{
    /// <summary>
    /// Well-known HeatPump IDs for testing.
    /// </summary>
    public static class HeatPumpIds
    {
        public static readonly HeatPumpId Default = HeatPumpId.From(Guid.Parse("11111111-1111-1111-1111-111111111111"));
        public static readonly HeatPumpId Secondary = HeatPumpId.From(Guid.Parse("22222222-2222-2222-2222-222222222222"));
        public static readonly HeatPumpId NonExistent = HeatPumpId.From(Guid.Parse("99999999-9999-9999-9999-999999999999"));
    }

    /// <summary>
    /// Well-known Sensor IDs for testing.
    /// </summary>
    public static class SensorIds
    {
        public static readonly SensorId Indoor = SensorId.From("sensor-indoor-main");
        public static readonly SensorId Outdoor = SensorId.From("sensor-outdoor-north");
        public static readonly SensorId BufferTank = SensorId.From("sensor-buffer-tank");
        public static readonly SensorId NonExistent = SensorId.From("sensor-does-not-exist");
    }

    /// <summary>
    /// Common temperature values for testing.
    /// </summary>
    public static class Temperatures
    {
        public static readonly Temperature RoomComfortable = Temperature.FromCelsius(21.0m);
        public static readonly Temperature RoomCold = Temperature.FromCelsius(16.0m);
        public static readonly Temperature RoomWarm = Temperature.FromCelsius(25.0m);

        public static readonly OutsideTemperature WinterCold = OutsideTemperature.FromCelsius(-10.0m);
        public static readonly OutsideTemperature WinterMild = OutsideTemperature.FromCelsius(5.0m);
        public static readonly OutsideTemperature SpringWarm = OutsideTemperature.FromCelsius(15.0m);
        public static readonly OutsideTemperature SummerHot = OutsideTemperature.FromCelsius(30.0m);

        public static readonly WaterTemperature HeatingInlet = WaterTemperature.FromCelsius(35.0m);
        public static readonly WaterTemperature HeatingOutlet = WaterTemperature.FromCelsius(30.0m);
        public static readonly WaterTemperature HeatingTarget = WaterTemperature.FromCelsius(38.0m);

        public static readonly DhwTemperature DhwActual = DhwTemperature.FromCelsius(48.0m);
        public static readonly DhwTemperature DhwTarget = DhwTemperature.FromCelsius(50.0m);
    }

    /// <summary>
    /// Common power values for testing.
    /// </summary>
    public static class Powers
    {
        public static readonly Power LowConsumption = Power.FromWatts(500);
        public static readonly Power MediumConsumption = Power.FromWatts(1000);
        public static readonly Power HighConsumption = Power.FromWatts(2000);

        public static readonly Power LowProduction = Power.FromWatts(1500);
        public static readonly Power MediumProduction = Power.FromWatts(3500);
        public static readonly Power HighProduction = Power.FromWatts(6000);

        public static PowerData EfficientHeating => new(
            MediumProduction,
            MediumConsumption,
            Power.Zero,
            Power.Zero,
            Power.Zero,
            Power.Zero);

        public static PowerData IneffcientHeating => new(
            LowProduction,
            HighConsumption,
            Power.Zero,
            Power.Zero,
            Power.Zero,
            Power.Zero);
    }

    /// <summary>
    /// Common date/time values for testing.
    /// </summary>
    public static class Times
    {
        public static readonly DateTimeOffset Reference = new(2024, 1, 15, 12, 0, 0, TimeSpan.Zero);
        public static readonly DateTimeOffset Yesterday = Reference.AddDays(-1);
        public static readonly DateTimeOffset LastWeek = Reference.AddDays(-7);
        public static readonly DateTimeOffset LastMonth = Reference.AddMonths(-1);

        public static DateTimeOffset MinutesAgo(int minutes) => DateTimeOffset.UtcNow.AddMinutes(-minutes);
        public static DateTimeOffset HoursAgo(int hours) => DateTimeOffset.UtcNow.AddHours(-hours);
        public static DateTimeOffset DaysAgo(int days) => DateTimeOffset.UtcNow.AddDays(-days);
    }

    /// <summary>
    /// Common operating scenarios for testing.
    /// </summary>
    public static class Scenarios
    {
        /// <summary>
        /// Normal winter heating scenario.
        /// </summary>
        public static CentralHeatingData WinterHeating => new(
            WaterTemperature.FromCelsius(38.0m),
            WaterTemperature.FromCelsius(32.0m),
            WaterTemperature.FromCelsius(40.0m));

        /// <summary>
        /// Mild weather low-demand scenario.
        /// </summary>
        public static CentralHeatingData MildWeatherHeating => new(
            WaterTemperature.FromCelsius(30.0m),
            WaterTemperature.FromCelsius(28.0m),
            WaterTemperature.FromCelsius(32.0m));

        /// <summary>
        /// DHW heating scenario.
        /// </summary>
        public static DomesticHotWaterData DhwHeating => new(
            DhwTemperature.FromCelsius(45.0m),
            DhwTemperature.FromCelsius(55.0m));

        /// <summary>
        /// DHW at target scenario.
        /// </summary>
        public static DomesticHotWaterData DhwAtTarget => new(
            DhwTemperature.FromCelsius(50.0m),
            DhwTemperature.FromCelsius(50.0m));
    }
}
