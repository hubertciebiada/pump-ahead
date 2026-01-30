namespace PumpAhead.DeepModel.ValueObjects;

/// <summary>
/// Operational statistics for heat pump.
/// HeishaMon TOP11-TOP12: Operations Hours/Counter.
/// </summary>
public readonly record struct OperationsData
{
    /// <summary>TOP11: Total compressor operating hours.</summary>
    public decimal CompressorHours { get; }

    /// <summary>TOP12: Total compressor start count.</summary>
    public int CompressorStarts { get; }

    public OperationsData(decimal compressorHours, int compressorStarts)
    {
        if (compressorHours < 0)
            throw new ArgumentOutOfRangeException(nameof(compressorHours), "Operating hours cannot be negative");
        if (compressorStarts < 0)
            throw new ArgumentOutOfRangeException(nameof(compressorStarts), "Start count cannot be negative");

        CompressorHours = compressorHours;
        CompressorStarts = compressorStarts;
    }

    public static OperationsData Zero => new(0, 0);

    public override string ToString() =>
        string.Format(System.Globalization.CultureInfo.InvariantCulture,
            "{0:F0}h / {1} starts", CompressorHours, CompressorStarts);
}
