# `requests` is a third-party HTTP library.
# HTTP is the request/response protocol used by web APIs. This app uses it to
# ask OpenWeatherMap for geocoding, current weather, and forecast data.
from datetime import datetime, timezone

import requests

# The OpenWeatherMap API key comes from `config.py`, which reads `.env` through
# environment variables loaded by `main.py`.
from config import OPENWEATHER_API_KEY, debug_print


# This endpoint converts a city or place name into latitude/longitude.
# One Call does not accept "Austin" directly, so we geocode first.
OPENWEATHER_GEOCODING_URL = "https://api.openweathermap.org/geo/1.0/direct"

# This is the endpoint URL for OpenWeatherMap One Call API 3.0.
# One Call can return current weather and daily forecasts in one API family.
OPENWEATHER_ONECALL_URL = "https://api.openweathermap.org/data/3.0/onecall"


def _missing_openweather_key() -> bool:
    """Return True when the OpenWeather API key is missing or still placeholder text."""
    return (
        not OPENWEATHER_API_KEY
        or OPENWEATHER_API_KEY == "your_openweathermap_api_key_here"
    )


def _hidden_url(url: str) -> str:
    """Return a debug-safe URL with the API key hidden."""
    return url.replace(OPENWEATHER_API_KEY, "[hidden]")


def _format_location(geo_result: dict) -> str:
    """Create a readable location name from OpenWeather geocoding data."""
    parts = [geo_result.get("name")]

    if geo_result.get("state"):
        parts.append(geo_result["state"])

    if geo_result.get("country"):
        parts.append(geo_result["country"])

    return ", ".join(part for part in parts if part)


def _format_date(timestamp: int, timezone_offset: int) -> str:
    """Convert a Unix timestamp into a local date string for the weather location."""
    return datetime.fromtimestamp(
        timestamp + timezone_offset,
        tz=timezone.utc,
    ).strftime("%Y-%m-%d")


def _geocode_location(location: str) -> dict:
    """Convert a user-provided place name into latitude and longitude.

    Parameter:
    - location: a city or place name, such as "Austin" or "New York".

    Return value:
    - On success, a dictionary with `name`, `lat`, and `lon`.
    - On failure, a dictionary with an `"error"` key.

    Why this is needed:
    OpenWeather One Call requires coordinates. Users naturally type city names,
    so this helper bridges the beginner-friendly user input and the coordinate-
    based API.
    """
    if not location or not location.strip():
        return {"error": "Please provide a location."}

    if _missing_openweather_key():
        return {
            "error": "OPENWEATHER_API_KEY is missing. Add your OpenWeatherMap API key to .env."
        }

    params = {
        "q": location.strip(),
        "limit": 1,
        "appid": OPENWEATHER_API_KEY,
    }
    debug_print("Prepared OpenWeatherMap geocoding request", {
        "url": OPENWEATHER_GEOCODING_URL,
        "params": {
            "q": params["q"],
            "limit": params["limit"],
            "appid": "[hidden]",
        },
    })

    try:
        response = requests.get(OPENWEATHER_GEOCODING_URL, params=params, timeout=10)
        debug_print("OpenWeatherMap geocoding HTTP response received", {
            "status_code": response.status_code,
            "url_without_api_key": _hidden_url(response.url),
        })

        data = response.json()
        debug_print("Parsed OpenWeatherMap geocoding JSON response", data)
    except requests.RequestException as exc:
        return {"error": f"Could not reach OpenWeatherMap geocoding: {exc}"}
    except ValueError:
        return {"error": "OpenWeatherMap geocoding returned a response that was not valid JSON."}

    if response.status_code != 200:
        message = data.get("message", "Unknown geocoding API error.")
        return {"error": f"OpenWeatherMap geocoding error: {message}"}

    if not data:
        return {"error": f"OpenWeatherMap could not find a location named '{location}'."}

    try:
        first_match = data[0]
        return {
            "name": _format_location(first_match),
            "lat": first_match["lat"],
            "lon": first_match["lon"],
        }
    except (KeyError, IndexError, TypeError):
        return {"error": "OpenWeatherMap returned an unexpected geocoding data format."}


def _get_onecall_weather(location: str, exclude: str) -> dict:
    """Fetch One Call weather data for a location name.

    Parameters:
    - location: the city/place name from the user.
    - exclude: a comma-separated One Call `exclude` value telling OpenWeather
      which blocks to leave out of the response.

    Return value:
    - On success, a dictionary with the geocoded location and One Call data.
    - On failure, a dictionary with an `"error"` key.
    """
    geocoded = _geocode_location(location)
    if "error" in geocoded:
        return geocoded

    params = {
        "lat": geocoded["lat"],
        "lon": geocoded["lon"],
        "appid": OPENWEATHER_API_KEY,
        "units": "imperial",
        "exclude": exclude,
    }
    debug_print("Prepared OpenWeatherMap One Call request", {
        "url": OPENWEATHER_ONECALL_URL,
        "params": {
            "lat": params["lat"],
            "lon": params["lon"],
            "appid": "[hidden]",
            "units": params["units"],
            "exclude": params["exclude"],
        },
    })

    try:
        response = requests.get(OPENWEATHER_ONECALL_URL, params=params, timeout=10)
        debug_print("OpenWeatherMap One Call HTTP response received", {
            "status_code": response.status_code,
            "url_without_api_key": _hidden_url(response.url),
        })

        data = response.json()
        debug_print("Parsed OpenWeatherMap One Call JSON response", data)
    except requests.RequestException as exc:
        return {"error": f"Could not reach OpenWeatherMap One Call: {exc}"}
    except ValueError:
        return {"error": "OpenWeatherMap One Call returned a response that was not valid JSON."}

    if response.status_code != 200:
        message = data.get("message", "Unknown One Call API error.")
        return {"error": f"OpenWeatherMap One Call error: {message}"}

    return {
        "location": geocoded["name"],
        "data": data,
    }


def get_current_weather(location: str) -> dict:
    """Fetch current weather from OpenWeatherMap One Call for a city or place name.

    Parameter:
    - location: a city or place name from the user, such as "Austin" or
      "New York". The LLM extracts this from the user's message and passes it
      through the tool-calling flow.

    Return value:
    - A Python dictionary. On success it contains clean weather fields the LLM
      can summarize. On failure it contains an `"error"` key with a readable
      explanation.

    How this fits the architecture:
    This is the tool/function the agent can call. The LLM decides *when* to use
    it, but this Python function does the actual live weather API request.
    """
    onecall_result = _get_onecall_weather(
        location,
        exclude="minutely,hourly,daily,alerts",
    )
    if "error" in onecall_result:
        return onecall_result

    data = onecall_result["data"]

    try:
        # Pull only the fields we want the LLM to use.
        #
        # OpenWeatherMap One Call returns a large nested JSON object. In Python:
        # - `data["current"]["temp"]` means get the `current` dictionary, then
        #   get its `temp` value.
        # - `data["current"]["weather"][0]["description"]` means get the first
        #   item from the `weather` list, then get its `description`.
        #
        # Returning a smaller dictionary keeps the final LLM prompt focused.
        current = data["current"]
        weather_result = {
            "location": onecall_result["location"],
            "temperature_f": current["temp"],
            "feels_like_f": current["feels_like"],
            "condition": current["weather"][0]["description"],
            "humidity": current["humidity"],
            "wind_speed_mph": current["wind_speed"],
        }
        debug_print("Weather tool normalized API data for the LLM", weather_result)
        return weather_result
    except (KeyError, IndexError, TypeError):
        # These errors mean the API responded with JSON, but not in the shape
        # the app expected:
        # - KeyError: a dictionary key was missing.
        # - IndexError: a list did not have the expected first item.
        # - TypeError: a value had the wrong type, such as None instead of dict.
        return {"error": "OpenWeatherMap returned an unexpected data format."}


def get_weather_forecast(
    location: str,
    days: int = 7,
    target_day_offset: int | None = None,
) -> dict:
    """Fetch a daily weather forecast from OpenWeatherMap One Call for up to 8 days.

    Parameters:
    - location: a city or place name, such as "Austin" or "New York".
    - days: how many forecast days to return, starting with today. One Call
      supports values from 1 through 8 for daily forecasts.
    - target_day_offset: optional index of a specific day to answer about,
      where 0 means today, 1 means tomorrow, and 2 means two days from now.

    Return value:
    - A Python dictionary containing the location, number of days requested, and
      a list of daily forecast dictionaries. If something goes wrong, the
      dictionary contains an `"error"` key instead.

    How this fits the architecture:
    This is a second tool the LLM can choose. The current-weather tool answers
    "what is happening now?" and this forecast tool answers "what will happen
    over the next few days?"
    """
    try:
        days = int(days)
    except (TypeError, ValueError):
        return {"error": "Forecast days must be a number from 1 to 8."}

    if days < 1 or days > 8:
        return {"error": "Forecast days must be between 1 and 8."}

    if target_day_offset is not None:
        try:
            target_day_offset = int(target_day_offset)
        except (TypeError, ValueError):
            return {"error": "Target day offset must be a number from 0 to 7."}

        if target_day_offset < 0 or target_day_offset > 7:
            return {"error": "Target day offset must be between 0 and 7."}

        days = max(days, target_day_offset + 1)

    onecall_result = _get_onecall_weather(
        location,
        exclude="current,minutely,hourly,alerts",
    )
    if "error" in onecall_result:
        return onecall_result

    data = onecall_result["data"]

    try:
        forecasts = []
        timezone_offset = data.get("timezone_offset", 0)

        daily_forecasts = data["daily"]

        for day_offset, daily_forecast in enumerate(daily_forecasts[:days]):
            weather = daily_forecast.get("weather") or [{}]
            forecasts.append(
                {
                    "day_offset": day_offset,
                    "date": _format_date(daily_forecast["dt"], timezone_offset),
                    "temperature_day_f": daily_forecast["temp"]["day"],
                    "temperature_min_f": daily_forecast["temp"]["min"],
                    "temperature_max_f": daily_forecast["temp"]["max"],
                    "feels_like_day_f": daily_forecast["feels_like"]["day"],
                    "condition": weather[0].get("description"),
                    "summary": daily_forecast.get("summary"),
                    "humidity": daily_forecast["humidity"],
                    "wind_speed_mph": daily_forecast["wind_speed"],
                    "chance_of_rain": daily_forecast.get("pop"),
                    "rain_inches": daily_forecast.get("rain", 0),
                }
            )

        forecast_result = {
            "location": onecall_result["location"],
            "days_requested": days,
            "days_returned": len(forecasts),
            "forecast": forecasts,
        }

        if target_day_offset is not None:
            try:
                forecast_result["target_day_offset"] = target_day_offset
                forecast_result["target_forecast"] = forecasts[target_day_offset]
            except IndexError:
                return {
                    "error": "OpenWeatherMap did not return enough forecast days for that request."
                }

        debug_print("Forecast tool normalized API data for the LLM", forecast_result)
        return forecast_result
    except (KeyError, IndexError, TypeError):
        return {"error": "OpenWeatherMap returned an unexpected forecast data format."}
