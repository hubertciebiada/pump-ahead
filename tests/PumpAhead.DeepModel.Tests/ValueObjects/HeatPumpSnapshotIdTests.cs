using FluentAssertions;
using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.DeepModel.Tests.ValueObjects;

public class HeatPumpSnapshotIdTests
{
    private const long ValidSnapshotId = 12345L;
    private const long ZeroId = 0L;
    private const long NegativeId = -1L;
    private const long AnotherValidId = 99999L;
    private const long FirstCompareId = 123L;
    private const long SecondCompareId = 456L;
    private const string ValidSnapshotIdString = "12345";

    #region Factory Method: From

    [Fact]
    public void From_GivenValidLong_ShouldCreateHeatPumpSnapshotId()
    {
        // Given
        var value = ValidSnapshotId;

        // When
        var result = HeatPumpSnapshotId.From(value);

        // Then
        result.Value.Should().Be(value);
    }

    [Fact]
    public void From_GivenZero_ShouldCreateHeatPumpSnapshotId()
    {
        // Given
        var value = ZeroId;

        // When
        var result = HeatPumpSnapshotId.From(value);

        // Then
        result.Value.Should().Be(0);
    }

    [Fact]
    public void From_GivenNegativeValue_ShouldCreateHeatPumpSnapshotId()
    {
        // Given
        var value = NegativeId;

        // When
        var result = HeatPumpSnapshotId.From(value);

        // Then
        result.Value.Should().Be(-1);
    }

    [Fact]
    public void From_GivenMaxValue_ShouldCreateHeatPumpSnapshotId()
    {
        // Given
        var value = long.MaxValue;

        // When
        var result = HeatPumpSnapshotId.From(value);

        // Then
        result.Value.Should().Be(long.MaxValue);
    }

    #endregion

    #region Constructor

    [Fact]
    public void Constructor_GivenValidLong_ShouldCreateHeatPumpSnapshotId()
    {
        // Given
        var value = AnotherValidId;

        // When
        var result = new HeatPumpSnapshotId(value);

        // Then
        result.Value.Should().Be(value);
    }

    #endregion

    #region Equality

    [Fact]
    public void Equals_GivenTwoSnapshotIdsWithSameValue_ShouldBeEqual()
    {
        // Given
        var value = ValidSnapshotId;
        var id1 = HeatPumpSnapshotId.From(value);
        var id2 = HeatPumpSnapshotId.From(value);

        // When & Then
        id1.Should().Be(id2);
        (id1 == id2).Should().BeTrue();
    }

    [Fact]
    public void Equals_GivenTwoSnapshotIdsWithDifferentValues_ShouldNotBeEqual()
    {
        // Given
        var id1 = HeatPumpSnapshotId.From(FirstCompareId);
        var id2 = HeatPumpSnapshotId.From(SecondCompareId);

        // When & Then
        id1.Should().NotBe(id2);
        (id1 != id2).Should().BeTrue();
    }

    #endregion

    #region GetHashCode

    [Fact]
    public void GetHashCode_GivenTwoSnapshotIdsWithSameValue_ShouldReturnSameHashCode()
    {
        // Given
        var value = ValidSnapshotId;
        var id1 = HeatPumpSnapshotId.From(value);
        var id2 = HeatPumpSnapshotId.From(value);

        // When
        var hashCode1 = id1.GetHashCode();
        var hashCode2 = id2.GetHashCode();

        // Then
        hashCode1.Should().Be(hashCode2);
    }

    [Fact]
    public void GetHashCode_GivenTwoSnapshotIdsWithDifferentValues_ShouldReturnDifferentHashCodes()
    {
        // Given
        var id1 = HeatPumpSnapshotId.From(FirstCompareId);
        var id2 = HeatPumpSnapshotId.From(SecondCompareId);

        // When
        var hashCode1 = id1.GetHashCode();
        var hashCode2 = id2.GetHashCode();

        // Then
        hashCode1.Should().NotBe(hashCode2);
    }

    #endregion

    #region ToString

    [Fact]
    public void ToString_GivenHeatPumpSnapshotId_ShouldReturnValueAsString()
    {
        // Given
        var value = ValidSnapshotId;
        var id = HeatPumpSnapshotId.From(value);

        // When
        var result = id.ToString();

        // Then
        result.Should().Be(ValidSnapshotIdString);
    }

    #endregion
}
