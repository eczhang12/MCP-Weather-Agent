# AGENTS.md

## Project Mission

This repo is a beginner-friendly weather agent learning project. The intended next version should teach MCP and LangChain by exposing the weather API functions as MCP tools, then loading those tools into a LangChain/LangGraph agent with `langchain-mcp-adapters`.

Keep the project approachable. Prefer clear, explicit Python over clever abstractions, and preserve the Docker-first workflow.

## Target Architecture

```text
main.py CLI
  -> agent/agent.py LangChain/LangGraph agent
  -> langchain-mcp-adapters MultiServerMCPClient
  -> mcp_server/server.py stdio MCP server
  -> mcp_server/weather_api.py OpenWeatherMap API helpers
```

The default user experience should remain:

```bash
python main.py
docker build -t weather-agent .
docker run --env-file .env -it weather-agent
```

## Repo Conventions

- Keep `main.py` as the terminal chat entry point.
- Keep configuration in `config.py`.
- Keep model behavior and prompts in `agent/`.
- Put MCP server code in `mcp_server/` unless a simpler local pattern emerges.
- Keep OpenWeatherMap API code reusable and separate from the agent loop.
- Keep comments useful for learners, especially around MCP, LangChain tool loading, async code, and Docker.
- Do not commit or print API keys.

## Dependencies

Expected Python dependencies for the MCP/LangChain version:

```text
langchain
langchain-openai
langgraph
langchain-mcp-adapters
mcp
python-dotenv
requests
```

Check current official docs before changing MCP or LangChain adapter code, because these APIs move:

- https://docs.langchain.com/oss/python/langchain/mcp
- https://reference.langchain.com/python/langchain-mcp-adapters/client/MultiServerMCPClient
- https://modelcontextprotocol.io/docs/sdk

## Implementation Notes

- Use a stdio MCP server by default. This keeps local and Docker usage simple because the LangChain app can spawn the MCP server as a child process.
- Expose weather functions as MCP tools with JSON-serializable return values.
- Use `MultiServerMCPClient` from `langchain_mcp_adapters.client` to load MCP tools.
- Use `langchain-openai` for the chat model.
- Prefer LangGraph's prebuilt ReAct agent if it fits cleanly.
- Preserve the existing weather features:
  - current weather
  - 1 to 8 day forecast
  - optional specific day forecast through `target_day_offset`
- Preserve debug logging behavior and keep API keys hidden.

## Validation

Run the lightest useful checks before finishing changes:

```bash
python -m compileall .
python main.py
python -m mcp_server.server
```

For Docker-related edits, also run:

```bash
docker build -t weather-agent .
docker run --env-file .env -it weather-agent
```

If network or API keys are unavailable, document exactly which checks could not be completed.

## Documentation Expectations

When converting the project, update `README.md` so a learner can answer:

- What changed from direct OpenAI function calling?
- What does the MCP server expose?
- How does LangChain discover and call MCP tools?
- How do I run the CLI locally?
- How do I run it in Docker?
- How do I smoke-test the MCP server directly?

Keep the README practical and command-driven.
