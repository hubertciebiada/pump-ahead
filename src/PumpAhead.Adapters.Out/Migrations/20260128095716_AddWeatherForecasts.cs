using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace PumpAhead.Adapters.Out.Migrations
{
    /// <inheritdoc />
    public partial class AddWeatherForecasts : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "WeatherForecasts",
                columns: table => new
                {
                    Id = table.Column<long>(type: "bigint", nullable: false)
                        .Annotation("SqlServer:Identity", "1, 1"),
                    TemperatureCelsius = table.Column<decimal>(type: "decimal(5,2)", precision: 5, scale: 2, nullable: false),
                    ForecastTimestamp = table.Column<DateTimeOffset>(type: "datetimeoffset", nullable: false),
                    FetchedAt = table.Column<DateTimeOffset>(type: "datetimeoffset", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_WeatherForecasts", x => x.Id);
                });

            migrationBuilder.CreateIndex(
                name: "IX_WeatherForecasts_FetchedAt",
                table: "WeatherForecasts",
                column: "FetchedAt");

            migrationBuilder.CreateIndex(
                name: "IX_WeatherForecasts_ForecastTimestamp",
                table: "WeatherForecasts",
                column: "ForecastTimestamp");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "WeatherForecasts");
        }
    }
}
