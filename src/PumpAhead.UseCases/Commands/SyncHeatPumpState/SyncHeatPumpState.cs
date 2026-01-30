using PumpAhead.DeepModel;
using PumpAhead.DeepModel.ValueObjects;
using PumpAhead.UseCases.Ports;
using PumpAhead.UseCases.Ports.Out;

namespace PumpAhead.UseCases.Commands.SyncHeatPumpState;

public static class SyncHeatPumpState
{
    public sealed record Command(HeishaMonData Data, HeatPumpId HeatPumpId);

    public sealed class Handler(
        IHeatPumpRepository heatPumpRepository,
        IHeatPumpNotificationService notificationService) : ICommandHandler<Command>
    {
        public async Task HandleAsync(Command command, CancellationToken cancellationToken = default)
        {
            var heatPump = await heatPumpRepository.GetByIdAsync(command.HeatPumpId, cancellationToken);

            if (heatPump is null)
                throw new InvalidOperationException($"HeatPump '{command.HeatPumpId.Value}' does not exist.");

            var data = command.Data;

            // Build Value Objects from raw data
            var centralHeating = new CentralHeatingData(
                WaterTemperature.FromCelsius(data.CH_InletTemperatureCelsius),
                WaterTemperature.FromCelsius(data.CH_OutletTemperatureCelsius),
                WaterTemperature.FromCelsius(data.CH_TargetTemperatureCelsius));

            var domesticHotWater = new DomesticHotWaterData(
                DhwTemperature.FromCelsius(data.DHW_ActualTemperatureCelsius),
                DhwTemperature.FromCelsius(data.DHW_TargetTemperatureCelsius));

            var power = new PowerData(
                Power.FromWatts(data.HeatPowerProductionWatts),
                Power.FromWatts(data.HeatPowerConsumptionWatts),
                Power.FromWatts(data.CoolPowerProductionWatts),
                Power.FromWatts(data.CoolPowerConsumptionWatts),
                Power.FromWatts(data.DhwPowerProductionWatts),
                Power.FromWatts(data.DhwPowerConsumptionWatts));

            var operations = new OperationsData(
                data.CompressorOperatingHours,
                data.CompressorStartCount);

            var defrost = new DefrostData(data.IsDefrosting);

            var errorCode = ErrorCode.From(data.ErrorCode);

            // Update aggregate
            heatPump.SyncFrom(
                data.IsOn,
                data.OperatingMode,
                PumpFlow.FromLitersPerMinute(data.PumpFlowLitersPerMinute),
                OutsideTemperature.FromCelsius(data.OutsideTemperatureCelsius),
                centralHeating,
                domesticHotWater,
                Frequency.FromHertz(data.CompressorFrequencyHertz),
                power,
                operations,
                defrost,
                errorCode);

            await heatPumpRepository.SaveAsync(heatPump, cancellationToken);
            await notificationService.NotifyHeatPumpUpdatedAsync();
        }
    }
}
