namespace PumpAhead.DeepModel.ValueObjects;

/// <summary>
/// Defrost cycle information.
/// HeishaMon TOP26: Defrosting_State.
/// </summary>
public readonly record struct DefrostData
{
    /// <summary>TOP26: Whether defrost cycle is currently active.</summary>
    public bool IsActive { get; }

    public DefrostData(bool isActive)
    {
        IsActive = isActive;
    }

    public static DefrostData Inactive => new(false);
    public static DefrostData Active => new(true);

    public override string ToString() => IsActive ? "Defrosting" : "Normal";
}
