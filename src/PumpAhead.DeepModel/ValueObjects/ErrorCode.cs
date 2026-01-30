namespace PumpAhead.DeepModel.ValueObjects;

/// <summary>
/// Heat pump error/alarm code.
/// HeishaMon TOP44: Error code.
/// </summary>
public readonly record struct ErrorCode
{
    /// <summary>
    /// The error code string. Empty string means no error.
    /// Format examples: "H00" (no error), "H15", "F12", etc.
    /// </summary>
    public string Code { get; }

    private ErrorCode(string code)
    {
        Code = code ?? string.Empty;
    }

    public static ErrorCode From(string? code) => new(code ?? string.Empty);
    public static ErrorCode None => new(string.Empty);

    /// <summary>
    /// Returns true if there is an active error (code is not empty and not "H00").
    /// </summary>
    public bool HasError => !string.IsNullOrWhiteSpace(Code) && Code != "H00";

    public override string ToString() => HasError ? Code : "OK";
}
