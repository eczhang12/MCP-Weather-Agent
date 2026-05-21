# `os` is a standard Python library for interacting with the operating system.
# Here we use it to read environment variables, which are configuration values
# stored outside the code. API keys are usually stored this way so they are not
# committed to GitHub or baked into the program.
import json
import os


# Read configuration from environment variables.
#
# `os.getenv("NAME", "")` means:
# - Look for an environment variable named NAME.
# - If it exists, return its string value.
# - If it does not exist, return the default value `""` instead.
#
# `python-dotenv` loads variables from `.env` in `main.py` before this module is
# imported by the application. After that, `os.getenv()` can read them as if they
# were normal shell environment variables.

# OpenAI uses this key to authenticate requests to the language model.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# OpenWeatherMap uses this key to authenticate live weather API requests.
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")

# This chooses which OpenAI model the weather agent should use.
# If `.env` does not define OPENAI_MODEL, the app falls back to "gpt-4.1-mini".
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

# This turns verbose debug logging on or off.
# It is read directly from `.env`, where you can set:
# WEATHER_AGENT_DEBUG=true
WEATHER_AGENT_DEBUG = os.getenv("WEATHER_AGENT_DEBUG", "false").lower() == "true"

# ANSI escape codes add color in most terminals, including Docker's interactive
# terminal output. They are just special text sequences that tell the terminal
# how to style what comes next.
DEBUG_COLOR_LABEL = "\x1B[33m"
DEBUG_COLOR = "\033[36m"
RESET_COLOR = "\033[0m"


def debug_print(label: str, value=None) -> None:
    """Print verbose debug output only when debug mode is enabled.

    Parameters:
    - label: a short description of the step being printed.
    - value: optional extra data, such as a dictionary, list, or string.

    Return value:
    - None. This function only prints to the terminal.

    How this fits the architecture:
    The weather agent has several request/response steps. This helper gives all
    modules one consistent way to show those steps while keeping normal output
    clean when debug mode is off.
    """
    if not WEATHER_AGENT_DEBUG:
        return

    print(f"{DEBUG_COLOR_LABEL}[debug] {label}{RESET_COLOR}")

    if value is None:
        return

    if isinstance(value, (dict, list)):
        print(f"{DEBUG_COLOR}{json.dumps(value, indent=2, default=str)}{RESET_COLOR}")
    else:
        print(f"{DEBUG_COLOR}{value}{RESET_COLOR}")
