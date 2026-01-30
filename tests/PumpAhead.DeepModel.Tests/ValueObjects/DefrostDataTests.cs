using FluentAssertions;
using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.DeepModel.Tests.ValueObjects;

public class DefrostDataTests
{
    private const string DefrostingStatus = "Defrosting";
    private const string NormalStatus = "Normal";

    #region Constructor

    [Fact]
    public void Constructor_GivenTrue_ShouldCreateActiveDefrostData()
    {
        // Given
        const bool isActive = true;

        // When
        var defrostData = new DefrostData(isActive);

        // Then
        defrostData.IsActive.Should().BeTrue();
    }

    [Fact]
    public void Constructor_GivenFalse_ShouldCreateInactiveDefrostData()
    {
        // Given
        const bool isActive = false;

        // When
        var defrostData = new DefrostData(isActive);

        // Then
        defrostData.IsActive.Should().BeFalse();
    }

    #endregion

    #region Factory Methods

    [Fact]
    public void Active_ShouldReturnDefrostDataWithIsActiveTrue()
    {
        // When
        var defrostData = DefrostData.Active;

        // Then
        defrostData.IsActive.Should().BeTrue();
    }

    [Fact]
    public void Inactive_ShouldReturnDefrostDataWithIsActiveFalse()
    {
        // When
        var defrostData = DefrostData.Inactive;

        // Then
        defrostData.IsActive.Should().BeFalse();
    }

    [Fact]
    public void Active_ShouldBeEquivalentToConstructorWithTrue()
    {
        // Given
        var fromFactory = DefrostData.Active;
        var fromConstructor = new DefrostData(true);

        // Then
        fromFactory.Should().Be(fromConstructor);
    }

    [Fact]
    public void Inactive_ShouldBeEquivalentToConstructorWithFalse()
    {
        // Given
        var fromFactory = DefrostData.Inactive;
        var fromConstructor = new DefrostData(false);

        // Then
        fromFactory.Should().Be(fromConstructor);
    }

    #endregion

    #region ToString

    [Fact]
    public void ToString_GivenActiveDefrost_ShouldReturnDefrosting()
    {
        // Given
        var defrostData = DefrostData.Active;

        // When
        var result = defrostData.ToString();

        // Then
        result.Should().Be(DefrostingStatus);
    }

    [Fact]
    public void ToString_GivenInactiveDefrost_ShouldReturnNormal()
    {
        // Given
        var defrostData = DefrostData.Inactive;

        // When
        var result = defrostData.ToString();

        // Then
        result.Should().Be(NormalStatus);
    }

    #endregion

    #region Equality

    [Fact]
    public void Equality_GivenTwoActiveInstances_ShouldBeEqual()
    {
        // Given
        var data1 = DefrostData.Active;
        var data2 = DefrostData.Active;

        // Then
        data1.Should().Be(data2);
    }

    [Fact]
    public void Equality_GivenTwoInactiveInstances_ShouldBeEqual()
    {
        // Given
        var data1 = DefrostData.Inactive;
        var data2 = DefrostData.Inactive;

        // Then
        data1.Should().Be(data2);
    }

    [Fact]
    public void Equality_GivenActiveAndInactive_ShouldNotBeEqual()
    {
        // Given
        var active = DefrostData.Active;
        var inactive = DefrostData.Inactive;

        // Then
        active.Should().NotBe(inactive);
    }

    #endregion
}
