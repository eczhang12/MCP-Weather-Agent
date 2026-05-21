from dotenv import load_dotenv


def print_startup_help() -> None:
    """Print beginner-friendly instructions before the chat loop starts.

    The `-> None` part is a Python type hint. It means this function is used
    for its side effect of printing text, and it does not return a value.

    This function is not part of the AI logic itself. It exists to help the
    human user understand how to run and stop the weather agent.
    """
    print("Weather Agent")
    print("-------------")
    print("Ask for current weather or a forecast, for example:")
    print('  "What is the weather in Austin?"')
    print('  "Give me the weather for New York"')
    print('  "Give me a 5 day forecast for Chicago"')
    print('  "What will the weather be like in Denver this weekend?"')
    print()
    print("Setup:")
    print("  1. Install dependencies: pip install -r requirements.txt")
    print("  2. Create .env with OPENAI_API_KEY and OPENWEATHER_API_KEY")
    print("  3. Run locally: python main.py")
    print("  4. Docker: docker build -t weather-agent .")
    print("             docker run --env-file .env -it weather-agent")
    print()
    print("Type 'quit' or 'exit' to stop.")
    print()


def missing_key(value: str, placeholder: str) -> bool:
    """Return True when an API key is missing or still set to a placeholder.

    Parameters:
    - value: the actual value read from an environment variable.
    - placeholder: the example text that appears in the README, such as
      "your_openai_api_key_here".

    Return value:
    - True means the key is not usable yet.
    - False means the key appears to contain a real value.

    """
    return not value or value == placeholder


def main() -> None:
    """Start the command-line weather agent.

    This is the main control center of the app:
    1. Load API keys from `.env`.
    2. Import configuration and the agent class.
    3. Check that required keys exist.
    4. Create one `WeatherAgent`.
    5. Repeatedly read user input and ask the agent to answer.
    """
    # Load `.env` before importing config-dependent modules.
    #
    # Why the order matters:
    # `config.py` reads environment variables as soon as it is imported. If we
    # imported `config.py` first and called `load_dotenv()` later, `config.py`
    # would see empty values instead of the keys from `.env`.
    load_dotenv()

    # These imports are intentionally inside `main()` and after `load_dotenv()`.
    # `WeatherAgent` imports `config.py`, and `config.py` reads the API keys.
    # This keeps the request/response flow configured before the agent starts.
    from agent.agent import WeatherAgent
    from config import (
        OPENAI_API_KEY,
        OPENWEATHER_API_KEY,
        WEATHER_AGENT_DEBUG,
        debug_print,
    )

    # Show setup and usage instructions before entering the interactive loop.
    print_startup_help()

    debug_print("Loaded configuration", {
        "openai_api_key_present": bool(OPENAI_API_KEY),
        "openweather_api_key_present": bool(OPENWEATHER_API_KEY),
        "weather_agent_debug": WEATHER_AGENT_DEBUG,
    })

    # Stop early if the OpenAI key is missing. The OpenAI key is required
    # because the language model decides whether to call the weather tool and
    # writes the final response for the user.
    if missing_key(OPENAI_API_KEY, "your_openai_api_key_here"):
        print("Missing OPENAI_API_KEY. Add it to your .env file before running.")
        return

    # Stop early if the OpenWeatherMap key is missing. This key is required
    # because the local weather tool calls OpenWeatherMap's API for live data.
    if missing_key(OPENWEATHER_API_KEY, "your_openweathermap_api_key_here"):
        print("Missing OPENWEATHER_API_KEY. Add it to your .env file before running.")
        return

    # Create the AI agent object once. It stores:
    # - an OpenAI client for talking to the model
    # - the model name
    # - the tool/function schema that tells the model a weather function exists
    agent = WeatherAgent()

    # This infinite loop keeps the command-line chat running until the user
    # types "quit" or "exit". Each loop iteration handles one user message.
    while True:
        # `input("You: ")` prints the prompt and waits for keyboard input.
        # `.strip()` removes extra spaces and the final newline.
        user_input = input("You: ").strip()
        debug_print("main.py received raw user input", user_input)

        # `.lower()` makes the comparison case-insensitive, so "QUIT",
        # "Quit", and "quit" all stop the app.
        # `{...}` creates a Python set, which is a simple collection of values.
        if user_input.lower() in {"quit", "exit"}:
            print("Goodbye!")
            break

        # If the user presses Enter on an empty line, skip this loop iteration
        # and ask again instead of sending an empty message to the model.
        if not user_input:
            continue

        try:
            # This is the important handoff from the command-line interface to
            # the agent architecture. `agent.run()` sends the user's text to
            # the LLM, handles any tool call, and returns a final string.
            debug_print("main.py is handing the input to WeatherAgent.run()")
            response = agent.run(user_input)
        except Exception as exc:
            # `except Exception as exc` catches unexpected runtime errors so
            # the beginner-facing app does not crash with a long traceback.
            # In a production app, you would usually log the full error too.
            response = f"Sorry, something went wrong: {exc}"

        # Print the final answer returned by the agent.
        print(f"Agent: {response}")
        print()


# This Python pattern means:
# "Only run `main()` when this file is executed directly with `python main.py`."
# If another file imports `main.py`, the functions become available but the
# chat loop does not start automatically.
if __name__ == "__main__":
    main()
