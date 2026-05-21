"""Compatibility wrappers for the CLI agent's weather tools.

The reusable OpenWeatherMap code now lives in `mcp_server.weather_api` so the
future MCP server and the existing CLI agent can share one source of truth.
Keeping these imports here means the rest of the current agent code can keep
using `from agent.tools import ...` exactly as before.
"""

from mcp_server.weather_api import get_current_weather, get_weather_forecast


__all__ = ["get_current_weather", "get_weather_forecast"]
