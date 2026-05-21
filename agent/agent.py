# `json` is a standard Python library for converting between:
# - JSON text, which APIs and LLM tool calls often use
# - Python values, such as dictionaries and strings
import json
from typing import Any

# `OpenAI` is the official client class from the `openai` package.
# It knows how to send HTTP requests to OpenAI's API and return Python objects.
from openai import OpenAI

# The system prompt gives the LLM its high-level instructions and boundaries.
from agent.prompts import SYSTEM_PROMPT

# This is the local Python function that actually calls the weather API.
# The LLM does not run this function directly. Instead, the LLM asks for a tool
# call, and our Python code decides whether and how to execute this function.
from agent.tools import get_current_weather, get_weather_forecast

# Configuration values come from environment variables loaded in `main.py`.
from config import OPENAI_API_KEY, OPENAI_MODEL, debug_print


class WeatherAgent:
    """A small OpenAI-powered agent that can call weather tools.

    In this project, an "agent" means a language model plus a little control
    loop around it. The language model reads the user's message and decides
    whether it needs outside information. The Python control loop gives the
    model a tool description, runs the requested tool, and sends the tool result
    back to the model so it can write a final answer.
    """

    def __init__(self):
        """Create the reusable OpenAI client and describe available tools.

        `__init__` is a special Python method called automatically when you run
        `WeatherAgent()`. It prepares the object for later calls to `run()`.

        There are no parameters besides `self`.
        - `self` means "this particular WeatherAgent object".
        - Values stored on `self`, such as `self.client`, can be used by other
          methods on the same object.
        """
        # Create an OpenAI API client. The API key tells OpenAI which account is
        # making the request. Without a valid key, model calls will fail.
        self.client = OpenAI(api_key=OPENAI_API_KEY)

        # Store the model name from configuration so the rest of the class does
        # not need to know where the setting came from.
        self.model = OPENAI_MODEL

        # `self.messages` is this agent's short-term conversation memory.
        #
        # Important idea:
        # The OpenAI model is stateless between API calls. It does not remember
        # the previous request unless we send the previous messages again.
        #
        # Because this list lives on the `WeatherAgent` object, it lasts for the
        # current terminal session/program run. It is not saved to a database or
        # file, so memory resets when the program exits.
        #
        # The system prompt stays at the beginning so every model call receives
        # the same high-level instructions.
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # `self.tools` is a list of tool definitions that will be sent to the
        # LLM. This does not execute the functions. It only describes the
        # functions so the model can decide whether one should be called.
        self.tools = [
            {
                # OpenAI's chat API supports different tool types. Here the
                # tool type is "function", meaning the model can request a
                # function call with structured arguments.
                "type": "function",  # ALWAYS FUNCTION
                "function": {
                    # This name must match the local function handling logic in
                    # `_handle_tool_call()`. The LLM will use this exact name if
                    # it decides current weather data is needed.
                    "name": "get_current_weather",

                    # The description teaches the LLM when this tool is useful.
                    # Clear descriptions make tool-calling agents more reliable.
                    "description": "Get the current live weather for a city or location.",

                    # `parameters` is a JSON Schema. It tells the LLM what
                    # arguments the function expects. In this case, the tool
                    # needs one string called `location`.
                    "parameters": {
                        "type": "object",  # says that it must be a JSON object, not a string or list
                        "properties": {  # Defines allowed fields
                            "location": {
                                "type": "string",
                                "description": "The city or location, such as Austin or New York.",
                            }
                        },
                        # `required` means the model should always provide a
                        # location when it requests this tool.
                        "required": ["location"],

                        # `additionalProperties: False` tells the model not to
                        # invent extra argument names beyond `location`.
                        "additionalProperties": False,
                    },
                },
            },
            {
                # This second tool is also a function tool. It is for forecast
                # questions like "What will the weather be like this weekend?"
                # or "Give me a 5 day forecast for Chicago."
                "type": "function",
                "function": {
                    "name": "get_weather_forecast",
                    "description": "Get a daily weather forecast for a city or location for 1 to 8 days.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "The city or location, such as Austin or New York.",
                            },
                            "days": {
                                "type": "integer",
                                "description": "The number of forecast days to return, starting with today, from 1 to 8.",
                                "minimum": 1,
                                "maximum": 8,
                            },
                            "target_day_offset": {
                                "type": "integer",
                                "description": "Use when the user asks about one specific future day. 0 means today, 1 means tomorrow, 2 means two days from now, up to 7.",
                                "minimum": 0,
                                "maximum": 7,
                            },
                        },
                        "required": ["location", "days"],
                        "additionalProperties": False,
                    },
                },
            },
        ]

        debug_print("WeatherAgent initialized", {
            "model": self.model,
            "available_tools": [
                tool["function"]["name"]
                for tool in self.tools
                if tool.get("type") == "function"
            ],
        })

    def run(self, user_input: str) -> str:
        """Send the user's message to the model and return the final answer.

        Parameter:
        - user_input: the text typed by the user, such as
          "What is the weather in Austin?"

        Return value:
        - A plain string that can be printed in the terminal.

        How this fits the architecture:
        This method is the main agent loop for one user request. It appends the
        user's message to the session memory, sends that memory to the LLM,
        checks whether the LLM asked to use a tool, runs any requested tool
        locally, then asks the LLM to write the final answer.
        """
        # `self.messages` is the conversation history sent to the chat model.
        # Each message has a `role`:
        # - "system" gives instructions to the assistant.
        # - "user" contains the human's request.
        # - "assistant" contains previous model responses or tool-call requests.
        # - "tool" contains the result returned by local Python tool functions.
        #
        # Appending the user message before the API call is what lets follow-up
        # questions work. For example, after "What is the weather in Chicago?",
        # a later "What about tomorrow?" can be understood because the earlier
        # Chicago turn is still in `self.messages`.
        self.messages.append({"role": "user", "content": user_input})
        debug_print("Appended user message to conversation memory", self._messages_to_debug_list(self.messages))

        # Ask the model what to do with the user's message.
        #
        # Important parameters:
        # - model: which OpenAI model to use.
        # - messages: the conversation so far.
        # - tools: the available function descriptions.
        # - tool_choice="auto": lets the model decide whether to call a tool or
        #   answer directly.
        first_response = self.client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            tools=self.tools,
            tool_choice="auto",
        )
        debug_print("OpenAI first response received")

        # The API returns a response object with one or more choices.
        # This app uses the first choice out of the many generated choices. `assistant_message` may contain either:
        # - normal assistant text, or
        # - one or more tool calls requested by the model.
        assistant_message = first_response.choices[0].message
        debug_print("Assistant message from first response", self._message_to_debug_dict(assistant_message))

        # If the model does not need a tool, return its answer directly.
        # For example, if the user asks "What can you do?", the model can answer
        # without live weather data.
        if not assistant_message.tool_calls: # checking if LLM Determined if tool should be used or not
            debug_print("No tool call requested; returning assistant response directly")
            self.messages.append(assistant_message)
            debug_print("Appended assistant response to conversation memory", self._messages_to_debug_list(self.messages))
            return assistant_message.content or "I am not sure how to answer that."

        # If the model did request a tool, save the assistant's tool-call
        # message in the conversation history. The next OpenAI request needs to
        # see that the assistant asked for the tool before it sees the tool
        # result.
        # Why?
        # The model is stateless between API calls—it does NOT remember that in the
        # previous request it decided to call a tool. The only "memory" it has is the
        # conversation history we explicitly send in `messages`.
        #
        # By appending this assistant message, we preserve the causal chain:
        #
        #   User: "What's the weather in Austin?"
        #   Assistant: "I want to call get_weather(city='Austin')"
        #   Tool: "72°F and sunny"
        #
        # When we make the next API call, the model can clearly see:
        # 1. what the user asked
        # 2. that it chose to call a specific tool
        # 3. which tool output belongs to that request
        #
        # Without this assistant tool-call message, the next request would look like:
        #
        #   User: "What's the weather in Austin?"
        #   Tool: "72°F and sunny"
        #
        # This breaks the reasoning chain because the model sees tool output with no
        # explanation of why it exists or what request it belongs to. That ambiguity
        # can lead to:
        # - worse responses
        # - incorrect reasoning
        # - mismatching tool outputs to requests
        # - failures when multiple tools are involved
        # - invalid tool-calling conversation structure
        self.messages.append(assistant_message)
        debug_print("Appended assistant tool-call message to preserve causal chain", self._messages_to_debug_list(self.messages))

        # A model can technically request multiple tools at once. This project
        # defines two tools, and looping keeps the code compatible with the API
        # shape if more tools are added later.
        for tool_call in assistant_message.tool_calls:
            # Run the local Python function requested by the LLM and get back a
            # Python dictionary, such as:
            # {"temperature_f": 72, "condition": "clear sky", ...}
            debug_print("Handling requested tool call", self._tool_call_to_debug_dict(tool_call))
            tool_result = self._handle_tool_call(tool_call)
            debug_print("Tool call returned result", tool_result)

            # Send the tool result back as a special "tool" role message.
            #
            # `tool_call_id` links this result to the exact tool call the model
            # requested. This is important when there are multiple tool calls.
            #
            # `json.dumps(tool_result)` converts the Python dictionary into a
            # JSON string because chat messages contain text, not raw Python
            # dictionaries.
            self.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result),
                }
            )
            debug_print("Appended tool result to conversation memory", self._messages_to_debug_list(self.messages))

        # Now ask the model a second time. This time the conversation includes:
        # 1. The system prompt.
        # 2. The user's weather question.
        # 3. The assistant's request to call a weather tool.
        # 4. The tool result containing live weather or forecast data.
        # AKA The entire Causal Chain is there so no inferring/poor reasoning will occur
        # 
        # The model uses that data to produce a natural-language response.
        debug_print("Sending updated conversation memory back to OpenAI for final answer", self._messages_to_debug_list(self.messages))
        final_response = self.client.chat.completions.create(
            model=self.model,
            messages=self.messages,
        )
        final_message = final_response.choices[0].message
        debug_print("OpenAI final response received", self._message_to_debug_dict(final_message))

        # Save the final assistant answer too. This is what lets future turns
        # refer back to what the assistant already told the user.
        self.messages.append(final_message)
        debug_print("Appended final assistant answer to conversation memory", self._messages_to_debug_list(self.messages))

        # Return the assistant's final text. The fallback string protects the
        # CLI from printing `None` if the API response has no content.
        return final_message.content or "I could not create a weather summary."

    def _handle_tool_call(self, tool_call) -> dict:
        """Run the local Python function requested by the model.

        Parameter:
        - tool_call: an object from OpenAI's response that contains:
          - the function name the model wants to call
          - the function arguments as a JSON string
          - an ID used to connect the tool result back to the request

        Return value:
        - A Python dictionary with either weather data or an error message.

        Why this method exists:
        The LLM is not allowed to directly execute arbitrary Python code. This
        method is the safety gate between "the model requested a tool" and "the
        app actually runs a local function".
        """
        # Read the function name requested by the model.
        function_name = tool_call.function.name
        debug_print("Tool handler received function name", function_name)

        # Only allow the tools this app explicitly supports. This prevents the
        # model from accidentally or maliciously requesting unknown code.
        if function_name not in {"get_current_weather", "get_weather_forecast"}:
            return {"error": f"Unknown tool requested: {function_name}"}

        try:
            # The model provides function arguments as JSON text, for example:
            # '{"location": "Austin"}'
            #
            # `json.loads()` parses that JSON string into a Python dictionary:
            # {"location": "Austin"}
            #
            # `or "{}"` means that if arguments is empty or None, parse an empty
            # JSON object instead of crashing immediately.
            arguments = json.loads(tool_call.function.arguments or "{}")
            debug_print("Parsed tool arguments from JSON", arguments)
        except json.JSONDecodeError:
            # If the model returns invalid JSON, the weather function cannot be
            # called safely because we do not know what arguments it intended.
            return {"error": "The model provided invalid tool arguments."}

        # Pull the `location` value out of the parsed arguments dictionary.
        # `.get("location")` returns None instead of raising an error if the
        # key is missing.
        location = arguments.get("location")

        # This is where the agent's tool call becomes a real API lookup.
        # The weather functions live in `agent/tools.py` and call
        # OpenWeatherMap over the internet.
        if function_name == "get_current_weather":
            return get_current_weather(location)

        days = arguments.get("days", 7)
        target_day_offset = arguments.get("target_day_offset")
        return get_weather_forecast(location, days, target_day_offset)

    def _messages_to_debug_list(self, messages: list[Any]) -> list[dict]:
        """Convert mixed message objects/dicts into printable debug dictionaries.

        The OpenAI client returns message objects, while this app also builds
        plain dictionaries. Debug output is easier to read when both shapes are
        normalized into dictionaries before printing.
        """
        return [self._message_to_debug_dict(message) for message in messages]

    def _message_to_debug_dict(self, message: Any) -> dict:
        """Return a JSON-friendly summary of one chat message for debug logs."""
        if isinstance(message, dict):
            return message

        return {
            "role": getattr(message, "role", None),
            "content": getattr(message, "content", None),
            "tool_calls": [
                self._tool_call_to_debug_dict(tool_call)
                for tool_call in (getattr(message, "tool_calls", None) or [])
            ],
        }

    def _tool_call_to_debug_dict(self, tool_call: Any) -> dict:
        """Return a JSON-friendly summary of a model-requested tool call."""
        function = getattr(tool_call, "function", None)
        return {
            "id": getattr(tool_call, "id", None),
            "type": getattr(tool_call, "type", None),
            "function": {
                "name": getattr(function, "name", None),
                "arguments": getattr(function, "arguments", None),
            },
        }
