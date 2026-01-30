using FluentAssertions;
using PumpAhead.DeepModel.ValueObjects;

namespace PumpAhead.DeepModel.Tests.ValueObjects;

public class ErrorCodeTests
{
    private const string H15ErrorCode = "H15";
    private const string H00ErrorCode = "H00";
    private const string F12ErrorCode = "F12";
    private const string EmptyErrorCode = "";
    private const string WhitespaceErrorCode = "   ";
    private const string OkStatus = "OK";

    #region None Static Property

    [Fact]
    public void None_ShouldReturnErrorCodeWithEmptyString()
    {
        // When
        var errorCode = ErrorCode.None;

        // Then
        errorCode.Code.Should().BeEmpty();
    }

    [Fact]
    public void None_ShouldNotHaveError()
    {
        // When
        var errorCode = ErrorCode.None;

        // Then
        errorCode.HasError.Should().BeFalse();
    }

    #endregion

    #region From Factory Method

    [Fact]
    public void From_GivenValidErrorCode_ShouldCreateErrorCodeWithValue()
    {
        // Given
        const string code = H15ErrorCode;

        // When
        var errorCode = ErrorCode.From(code);

        // Then
        errorCode.Code.Should().Be(H15ErrorCode);
    }

    [Fact]
    public void From_GivenNull_ShouldReturnErrorCodeWithEmptyString()
    {
        // Given
        string? code = null;

        // When
        var errorCode = ErrorCode.From(code);

        // Then
        errorCode.Code.Should().BeEmpty();
    }

    [Fact]
    public void From_GivenEmptyString_ShouldReturnErrorCodeWithEmptyString()
    {
        // Given
        const string code = EmptyErrorCode;

        // When
        var errorCode = ErrorCode.From(code);

        // Then
        errorCode.Code.Should().BeEmpty();
    }

    [Fact]
    public void From_GivenH00_ShouldCreateErrorCodeWithH00Value()
    {
        // Given
        const string code = H00ErrorCode;

        // When
        var errorCode = ErrorCode.From(code);

        // Then
        errorCode.Code.Should().Be(H00ErrorCode);
    }

    [Theory]
    [InlineData("F12")]
    [InlineData("H15")]
    [InlineData("F93")]
    [InlineData("H62")]
    public void From_GivenVariousErrorCodes_ShouldCreateErrorCodeWithCorrectValue(string code)
    {
        // When
        var errorCode = ErrorCode.From(code);

        // Then
        errorCode.Code.Should().Be(code);
    }

    #endregion

    #region HasError Property

    [Fact]
    public void HasError_GivenEmptyCode_ShouldReturnFalse()
    {
        // Given
        var errorCode = ErrorCode.From(EmptyErrorCode);

        // Then
        errorCode.HasError.Should().BeFalse();
    }

    [Fact]
    public void HasError_GivenH00_ShouldReturnFalse()
    {
        // Given - H00 means "no error" in Panasonic heat pumps
        var errorCode = ErrorCode.From(H00ErrorCode);

        // Then
        errorCode.HasError.Should().BeFalse();
    }

    [Fact]
    public void HasError_GivenWhitespaceOnly_ShouldReturnFalse()
    {
        // Given
        var errorCode = ErrorCode.From(WhitespaceErrorCode);

        // Then
        errorCode.HasError.Should().BeFalse();
    }

    [Theory]
    [InlineData("H15")]
    [InlineData("F12")]
    [InlineData("F93")]
    [InlineData("H62")]
    [InlineData("F40")]
    public void HasError_GivenActualErrorCode_ShouldReturnTrue(string code)
    {
        // Given
        var errorCode = ErrorCode.From(code);

        // Then
        errorCode.HasError.Should().BeTrue();
    }

    [Fact]
    public void HasError_GivenNone_ShouldReturnFalse()
    {
        // Given
        var errorCode = ErrorCode.None;

        // Then
        errorCode.HasError.Should().BeFalse();
    }

    #endregion

    #region ToString

    [Fact]
    public void ToString_GivenNoError_ShouldReturnOK()
    {
        // Given
        var errorCode = ErrorCode.None;

        // When
        var result = errorCode.ToString();

        // Then
        result.Should().Be(OkStatus);
    }

    [Fact]
    public void ToString_GivenH00_ShouldReturnOK()
    {
        // Given
        var errorCode = ErrorCode.From(H00ErrorCode);

        // When
        var result = errorCode.ToString();

        // Then
        result.Should().Be(OkStatus);
    }

    [Fact]
    public void ToString_GivenActualError_ShouldReturnTheErrorCode()
    {
        // Given
        var errorCode = ErrorCode.From(F12ErrorCode);

        // When
        var result = errorCode.ToString();

        // Then
        result.Should().Be(F12ErrorCode);
    }

    [Theory]
    [InlineData("H15", "H15")]
    [InlineData("F93", "F93")]
    [InlineData("H62", "H62")]
    public void ToString_GivenVariousErrors_ShouldReturnCorrectCode(string code, string expected)
    {
        // Given
        var errorCode = ErrorCode.From(code);

        // When
        var result = errorCode.ToString();

        // Then
        result.Should().Be(expected);
    }

    #endregion

    #region Equality

    [Fact]
    public void Equality_GivenSameCodes_ShouldBeEqual()
    {
        // Given
        var code1 = ErrorCode.From(H15ErrorCode);
        var code2 = ErrorCode.From(H15ErrorCode);

        // Then
        code1.Should().Be(code2);
    }

    [Fact]
    public void Equality_GivenDifferentCodes_ShouldNotBeEqual()
    {
        // Given
        var code1 = ErrorCode.From(H15ErrorCode);
        var code2 = ErrorCode.From(F12ErrorCode);

        // Then
        code1.Should().NotBe(code2);
    }

    [Fact]
    public void Equality_GivenNoneAndEmptyString_ShouldBeEqual()
    {
        // Given
        var none = ErrorCode.None;
        var empty = ErrorCode.From(EmptyErrorCode);

        // Then
        none.Should().Be(empty);
    }

    [Fact]
    public void Equality_GivenNoneAndNull_ShouldBeEqual()
    {
        // Given
        var none = ErrorCode.None;
        var fromNull = ErrorCode.From(null);

        // Then
        none.Should().Be(fromNull);
    }

    #endregion
}
