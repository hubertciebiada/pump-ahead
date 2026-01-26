using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace PumpAhead.Adapters.Out.Migrations
{
    /// <inheritdoc />
    public partial class RemoveHumidityColumn : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "Humidity",
                table: "TemperatureReadings");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<decimal>(
                name: "Humidity",
                table: "TemperatureReadings",
                type: "decimal(5,2)",
                precision: 5,
                scale: 2,
                nullable: true);
        }
    }
}
