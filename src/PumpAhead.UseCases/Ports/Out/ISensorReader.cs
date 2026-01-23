using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.UseCases.Ports.Out;

public interface ISensorReader
{
    Task<Temperature> ReadTemperatureAsync(CancellationToken cancellationToken = default);
}
