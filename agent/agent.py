"""LangChain weather agent that uses tools from the local MCP server."""

import asyncio
import os
import sys
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI

from agent.prompts import SYSTEM_PROMPT
from config import OPENAI_API_KEY, OPENAI_MODEL, debug_print


class LangChainMCPWeatherAgent:
    """A small LangChain agent that discovers weather tools through MCP.

    The important learning idea:
    - LangChain handles the model and the agent loop.
    - MCP describes and runs the weather tools.
    - This class connects those two pieces and keeps short-term chat memory.
    """

    def __init__(self) -> None:
        """Create the model, MCP client, and in-memory conversation state."""
        # MultiServerMCPClient can connect to one or more MCP servers. This
        # project only has one server named "weather".
        #
        # The stdio transport starts `python -m mcp_server.server` as a child
        # process. The agent talks to that process through standard input and
        # output, so no web server or port is needed.
        self.mcp_client = MultiServerMCPClient(
            {
                "weather": {
                    "transport": "stdio",
                    "command": sys.executable,
                    "args": ["-m", "mcp_server.server"],
                    # Pass the current environment to the MCP subprocess so it
                    # can read OPENWEATHER_API_KEY and debug settings.
                    "env": os.environ.copy(),
                }
            }
        )

        # ChatOpenAI is LangChain's wrapper around the OpenAI chat model.
        self.model = ChatOpenAI(
            model=OPENAI_MODEL,
            api_key=OPENAI_API_KEY,
        )

        # This list is the terminal session's memory. It is intentionally simple
        # and temporary: no database, no files, and nothing survives a restart.
        self.messages: list[Any] = []

        # These start as None because loading MCP tools starts a subprocess.
        # We wait until the first user request so startup stays lightweight.
        self.tools: list[Any] | None = None
        self.agent = None

    async def load_mcp_tools(self) -> list[Any]:
        """Ask the MCP server which tools it exposes, then cache the result."""
        if self.tools is None:
            self.tools = await self.mcp_client.get_tools()
            debug_print(
                "LangChain MCP agent loaded tools",
                [tool.name for tool in self.tools],
            )

        return self.tools

    async def _get_agent(self):
        """Build the LangChain agent after the MCP tools are available."""
        if self.agent is None:
            tools = await self.load_mcp_tools()

            # `create_agent` gives the model the tool list and system prompt.
            # During a run, the model can choose to call an MCP weather tool
            # before writing its final answer.
            self.agent = create_agent(
                model=self.model,
                tools=tools,
                system_prompt=SYSTEM_PROMPT,
            )
            debug_print("LangChain MCP agent initialized")

        return self.agent

    async def arun(self, user_input: str) -> str:
        """Answer one user message using LangChain and MCP tools."""
        agent = await self._get_agent()

        # Add the user's message to the same list each turn. Reusing this list
        # is what lets follow-up questions work, such as "What about tomorrow?"
        # after asking about Austin.
        self.messages.append(HumanMessage(content=user_input))

        # LangChain runs the model, handles any MCP tool calls, appends tool
        # results to the message list, and returns the updated conversation.
        response = await agent.ainvoke({"messages": self.messages})
        self.messages = response["messages"]

        final_message = self.messages[-1]
        if isinstance(final_message, AIMessage):
            return final_message.content or "I could not create a weather summary."

        return str(getattr(final_message, "content", final_message))

    def run(self, user_input: str) -> str:
        """Synchronous helper for simple scripts that are not using asyncio."""
        return asyncio.run(self.arun(user_input))
