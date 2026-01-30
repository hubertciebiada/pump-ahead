using FluentAssertions;
using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.DeepModel.Tests.ValueObjects;

public class SensorIdTests
{
    private const string ValidSensorId = "sensor-123";
    private const string SensorOne = "sensor-1";
    private const string SensorTwo = "sensor-2";
    private const string SensorOnePascalCase = "Sensor-1";
    private const string WhitespaceString = "   ";

    #region Factory Method: From

    [Fact]
    public void From_GivenValidString_ShouldCreateSensorId()
    {
        // Given
        var value = ValidSensorId;

        // When
        var result = SensorId.From(value);

        // Then
        result.Value.Should().Be(value);
    }

    [Fact]
    public void From_GivenNullString_ShouldThrowArgumentException()
    {
        // Given
        string? value = null;

        // When
        var act = () => SensorId.From(value!);

        // Then
        act.Should().Throw<ArgumentException>();
    }

    [Fact]
    public void From_GivenEmptyString_ShouldThrowArgumentException()
    {
        // Given
        var value = string.Empty;

        // When
        var act = () => SensorId.From(value);

        // Then
        act.Should().Throw<ArgumentException>();
    }

    [Fact]
    public void From_GivenWhitespaceString_ShouldThrowArgumentException()
    {
        // Given
        var value = WhitespaceString;

        // When
        var act = () => SensorId.From(value);

        // Then
        act.Should().Throw<ArgumentException>();
    }

    [Theory]
    [InlineData("sensor-1")]
    [InlineData("TEMP_OUTDOOR")]
    [InlineData("cwu.actual")]
    [InlineData("28-00000a7b3c15")]
    public void From_GivenVariousValidStrings_ShouldCreateSensorId(string value)
    {
        // When
        var result = SensorId.From(value);

        // Then
        result.Value.Should().Be(value);
    }

    #endregion

    #region Equality

    [Fact]
    public void Equals_GivenTwoSensorIdsWithSameValue_ShouldBeEqual()
    {
        // Given
        var value = ValidSensorId;
        var id1 = SensorId.From(value);
        var id2 = SensorId.From(value);

        // When & Then
        id1.Should().Be(id2);
        (id1 == id2).Should().BeTrue();
    }

    [Fact]
    public void Equals_GivenTwoSensorIdsWithDifferentValues_ShouldNotBeEqual()
    {
        // Given
        var id1 = SensorId.From(SensorOne);
        var id2 = SensorId.From(SensorTwo);

        // When & Then
        id1.Should().NotBe(id2);
        (id1 != id2).Should().BeTrue();
    }

    [Fact]
    public void Equals_GivenSensorIdsWithDifferentCase_ShouldNotBeEqual()
    {
        // Given
        var id1 = SensorId.From(SensorOnePascalCase);
        var id2 = SensorId.From(SensorOne);

        // When & Then
        id1.Should().NotBe(id2);
    }

    #endregion

    #region GetHashCode

    [Fact]
    public void GetHashCode_GivenTwoSensorIdsWithSameValue_ShouldReturnSameHashCode()
    {
        // Given
        var value = ValidSensorId;
        var id1 = SensorId.From(value);
        var id2 = SensorId.From(value);

        // When
        var hashCode1 = id1.GetHashCode();
        var hashCode2 = id2.GetHashCode();

        // Then
        hashCode1.Should().Be(hashCode2);
    }

    [Fact]
    public void GetHashCode_GivenTwoSensorIdsWithDifferentValues_ShouldReturnDifferentHashCodes()
    {
        // Given
        var id1 = SensorId.From(SensorOne);
        var id2 = SensorId.From(SensorTwo);

        // When
        var hashCode1 = id1.GetHashCode();
        var hashCode2 = id2.GetHashCode();

        // Then
        hashCode1.Should().NotBe(hashCode2);
    }

    #endregion

    #region ToString

    [Fact]
    public void ToString_GivenSensorId_ShouldReturnValueAsString()
    {
        // Given
        var value = ValidSensorId;
        var id = SensorId.From(value);

        // When
        var result = id.ToString();

        // Then
        result.Should().Be(value);
    }

    #endregion
}
