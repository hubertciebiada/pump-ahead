using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace PumpAhead.Adapters.Out.Migrations
{
    /// <inheritdoc />
    public partial class AddSensorLabel : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "Label",
                table: "Sensors",
                type: "nvarchar(100)",
                maxLength: 100,
                nullable: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "Label",
                table: "Sensors");
        }
    }
}
