"""MCP server that exposes this project's weather functions as tools.

MCP stands for Model Context Protocol. It is a standard way for AI apps to
discover and call external tools, such as local Python functions, databases, or
web API helpers.

This file does not contain OpenWeatherMap logic. It only adapts the reusable
functions from `weather_api.py` into MCP tools.
"""

from mcp.server.fastmcp import FastMCP

from mcp_server.weather_api import (
    get_current_weather as fetch_current_weather,
    get_weather_forecast as fetch_weather_forecast,
)


# FastMCP is the beginner-friendly server class from the Python MCP SDK.
# The name helps MCP clients identify this server when they connect to it.
mcp = FastMCP("weather-agent")


@mcp.tool()
def get_current_weather(location: str) -> dict:
    """Get the current live weather for a city or location."""
    # An MCP tool is a normal Python function that the MCP server advertises to
    # clients. The client can inspect the function name, description, and type
    # hints, then ask the server to run it with JSON arguments.
    return fetch_current_weather(location)


@mcp.tool()
def get_weather_forecast(
    location: str,
    days: int = 7,
    target_day_offset: int | None = None,
) -> dict:
    """Get a daily weather forecast for a city or location for 1 to 8 days."""
    return fetch_weather_forecast(
        location=location,
        days=days,
        target_day_offset=target_day_offset,
    )


def main() -> None:
    """Start the MCP server with stdio transport.

    Stdio means "standard input and standard output." For a local learning
    project, this is simpler than running an HTTP service because the MCP client
    can start this Python process and talk to it through normal process pipes.
    """
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
