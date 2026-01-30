using FluentAssertions;
using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.DeepModel.Tests.ValueObjects;

public class HeatPumpIdTests
{
    private const string CannotBeEmptyMessage = "*cannot be empty*";

    #region Factory Method: From

    [Fact]
    public void From_GivenValidGuid_ShouldCreateHeatPumpId()
    {
        // Given
        var guid = Guid.NewGuid();

        // When
        var result = HeatPumpId.From(guid);

        // Then
        result.Value.Should().Be(guid);
    }

    [Fact]
    public void From_GivenEmptyGuid_ShouldThrowArgumentException()
    {
        // Given
        var emptyGuid = Guid.Empty;

        // When
        var act = () => HeatPumpId.From(emptyGuid);

        // Then
        act.Should().Throw<ArgumentException>()
            .WithMessage(CannotBeEmptyMessage);
    }

    #endregion

    #region Factory Method: NewId

    [Fact]
    public void NewId_WhenCalled_ShouldCreateHeatPumpIdWithNonEmptyGuid()
    {
        // When
        var result = HeatPumpId.NewId();

        // Then
        result.Value.Should().NotBe(Guid.Empty);
    }

    [Fact]
    public void NewId_WhenCalledMultipleTimes_ShouldCreateUniqueIds()
    {
        // When
        var id1 = HeatPumpId.NewId();
        var id2 = HeatPumpId.NewId();

        // Then
        id1.Should().NotBe(id2);
    }

    #endregion

    #region Equality

    [Fact]
    public void Equals_GivenTwoHeatPumpIdsWithSameGuid_ShouldBeEqual()
    {
        // Given
        var guid = Guid.NewGuid();
        var id1 = HeatPumpId.From(guid);
        var id2 = HeatPumpId.From(guid);

        // When & Then
        id1.Should().Be(id2);
        (id1 == id2).Should().BeTrue();
    }

    [Fact]
    public void Equals_GivenTwoHeatPumpIdsWithDifferentGuids_ShouldNotBeEqual()
    {
        // Given
        var id1 = HeatPumpId.From(Guid.NewGuid());
        var id2 = HeatPumpId.From(Guid.NewGuid());

        // When & Then
        id1.Should().NotBe(id2);
        (id1 != id2).Should().BeTrue();
    }

    #endregion

    #region GetHashCode

    [Fact]
    public void GetHashCode_GivenTwoHeatPumpIdsWithSameGuid_ShouldReturnSameHashCode()
    {
        // Given
        var guid = Guid.NewGuid();
        var id1 = HeatPumpId.From(guid);
        var id2 = HeatPumpId.From(guid);

        // When
        var hashCode1 = id1.GetHashCode();
        var hashCode2 = id2.GetHashCode();

        // Then
        hashCode1.Should().Be(hashCode2);
    }

    [Fact]
    public void GetHashCode_GivenTwoHeatPumpIdsWithDifferentGuids_ShouldReturnDifferentHashCodes()
    {
        // Given
        var id1 = HeatPumpId.From(Guid.NewGuid());
        var id2 = HeatPumpId.From(Guid.NewGuid());

        // When
        var hashCode1 = id1.GetHashCode();
        var hashCode2 = id2.GetHashCode();

        // Then
        hashCode1.Should().NotBe(hashCode2);
    }

    #endregion

    #region ToString

    [Fact]
    public void ToString_GivenHeatPumpId_ShouldReturnGuidAsString()
    {
        // Given
        var guid = Guid.NewGuid();
        var id = HeatPumpId.From(guid);

        // When
        var result = id.ToString();

        // Then
        result.Should().Be(guid.ToString());
    }

    #endregion
}
