namespace PumpAhead.DeepModel.ValueObjects;

public readonly record struct CompressorData
{
    public Frequency Frequency { get; }

    private CompressorData(Frequency frequency)
    {
        Frequency = frequency;
    }

    public static CompressorData Create(Frequency frequency) => new(frequency);
}
