"""Smoke-test the local MCP weather server over stdio.

Run from the project root after installing dependencies:

    python tests/test_mcp_server.py

Or run inside Docker:

    docker run --env-file .env weather-agent python tests/test_mcp_server.py

This is intentionally a small script, not a full test suite. Its job is to
prove the basic MCP path works:

1. Start the MCP server as a child process.
2. Connect with the MCP client SDK over stdio.
3. List the tools the server exposes.
4. Call one weather tool and print the result.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _print_tool_result(result: types.CallToolResult) -> None:
    """Print an MCP tool result in a readable way for beginners."""
    if result.structuredContent is not None:
        print(json.dumps(result.structuredContent, indent=2))
        return

    for content in result.content:
        if isinstance(content, types.TextContent):
            print(content.text)
        else:
            print(content)


async def main() -> None:
    """Launch the MCP server, list tools, and call current weather."""
    # Load `.env` so the child MCP server receives OPENWEATHER_API_KEY.
    load_dotenv(PROJECT_ROOT / ".env")

    env = os.environ.copy()
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server.server"],
        env=env,
        cwd=PROJECT_ROOT,
    )

    print("Starting MCP weather server over stdio...")

    # `stdio_client` starts the server subprocess and gives us read/write
    # streams. `ClientSession` speaks the MCP protocol over those streams.
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            print("Initializing MCP session...")
            await session.initialize()

            print("Listing available tools...")
            tools_response = await session.list_tools()
            tool_names = [tool.name for tool in tools_response.tools]
            print(f"Tools: {tool_names}")

            required_tools = {"get_current_weather", "get_weather_forecast"}
            missing_tools = required_tools.difference(tool_names)
            if missing_tools:
                raise RuntimeError(f"Missing expected MCP tools: {sorted(missing_tools)}")

            print('Calling get_current_weather("Austin")...')
            result = await session.call_tool(
                "get_current_weather",
                arguments={"location": "Austin"},
            )

            print("Tool call result:")
            _print_tool_result(result)

            if result.isError:
                raise RuntimeError("MCP tool call returned an error result.")

    print("MCP smoke test completed successfully.")


if __name__ == "__main__":
    asyncio.run(main())
