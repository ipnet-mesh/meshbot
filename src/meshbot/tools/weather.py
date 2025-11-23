"""Weather tool for getting forecast information."""

import logging
from typing import Any, Optional

from pydantic_ai import RunContext

logger = logging.getLogger(__name__)

try:
    import aiohttp
except ImportError:
    aiohttp = None


def register_weather_tool(agent: Any) -> None:
    """Register weather tool.

    Args:
        agent: The Pydantic AI agent to register tools with
    """

    @agent.tool
    async def get_weather(
        ctx: RunContext[Any],
        location: str = "current",
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        forecast_days: int = 3,
    ) -> str:
        """Get weather forecast using Open-Meteo API.

        Args:
            location: Location name (default: current location from env vars)
            latitude: Latitude override (default: from env var)
            longitude: Longitude override (default: from env var)
            forecast_days: Number of forecast days (default: 3)

        Returns:
            Concise weather summary with forecast
        """
        logger.info(
            f"🌤️ TOOL CALL: get_weather(location='{location}', lat={latitude}, lon={longitude}, days={forecast_days})"
        )
        try:
            import os

            # Check if aiohttp is available
            if not aiohttp:
                return "Weather service unavailable (aiohttp not installed)"

            # Get coordinates from parameters or environment
            if latitude is not None and longitude is not None:
                lat, lon = latitude, longitude
            elif location == "current":
                # Try to get coordinates from environment variables
                lat = float(
                    os.getenv("WEATHER_LATITUDE", "51.5074")
                )  # Default to London
                lon = float(
                    os.getenv("WEATHER_LONGITUDE", "-0.1278")
                )  # Default to London
            else:
                # For named locations, use predefined coordinates
                locations = {
                    "london": (51.5074, -0.1278),
                    "manchester": (53.4808, -2.2426),
                    "cambridge": (52.2053, 0.1218),
                    "birmingham": (52.4862, -1.8904),
                    "glasgow": (55.8642, -4.2518),
                    "liverpool": (53.4084, -2.9916),
                    "leeds": (53.7966, -1.7532),
                    "sheffield": (53.3811, -1.4701),
                    "bristol": (51.4545, -2.5879),
                    "cardiff": (51.4816, -3.1791),
                    "belfast": (54.5970, -5.9300),
                    "newcastle": (54.9783, -1.6174),
                    "nottingham": (52.9508, -1.1438),
                    "leicester": (52.6369, -1.0979),
                    "coventry": (52.4068, -1.5120),
                    "southampton": (50.9097, -1.4044),
                    "portsmouth": (50.7957, -1.1077),
                    "reading": (51.4543, -0.9781),
                    "oxford": (51.7520, -1.2577),
                    "brighton": (50.8288, -0.1346),
                    "ipswich": (52.0597, 1.1455),
                }

                location_key = location.lower().replace(" ", "")
                if location_key in locations:
                    lat, lon = locations[location_key]
                else:
                    return f"Unknown location: {location}. Available: {', '.join(locations.keys())}"

            # Get forecast days from environment or parameter
            days = int(os.getenv("WEATHER_FORECAST_DAYS", str(forecast_days)))

            # Build Open-Meteo API URL - request daily data
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,wind_speed_10m,precipitation&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_speed_10m_max&forecast_days={days}&timezone=auto"
            logger.info(f"🌐 Open-Meteo API request: {url}")

            # Make HTTP request
            try:
                logger.info("🌐 Creating aiohttp session...")
                async with aiohttp.ClientSession() as session:
                    logger.info(f"🌐 Making HTTP request to: {url}")
                    async with session.get(url, timeout=15) as response:
                        logger.info(f"🌐 HTTP response status: {response.status}")
                        if response.status != 200:
                            logger.error(f"🌐 HTTP error: {response.status}")
                            return f"Weather service error: HTTP {response.status}"

                        data = await response.json()
                        logger.info(
                            f"🌐 Open-Meteo response received: {len(str(data))} chars"
                        )

                        # Extract current weather
                        if "current" not in data:
                            logger.error(f"🌐 No current field in response: {data.keys()}")
                            return "Weather data unavailable"

                        current = data["current"]
                        temp_current = current.get("temperature_2m", "N/A")
                        wind_current = current.get("wind_speed_10m", 0) * 2.237  # Convert m/s to mph
                        precip_current = current.get("precipitation", 0)

                        # Extract daily forecast
                        daily = data.get("daily", {})
                        if not daily:
                            logger.error(f"🌐 No daily field in response")
                            return "Forecast data unavailable"

                        dates = daily.get("time", [])
                        temp_max = daily.get("temperature_2m_max", [])
                        temp_min = daily.get("temperature_2m_min", [])
                        precip_prob = daily.get("precipitation_probability_max", [])
                        wind_max = daily.get("wind_speed_10m_max", [])

                        # Build forecast summary
                        forecast_summary = ""
                        for i in range(min(days, len(dates))):
                            date_str = dates[i] if i < len(dates) else "?"
                            max_temp = temp_max[i] if i < len(temp_max) else "?"
                            min_temp = temp_min[i] if i < len(temp_min) else "?"
                            rain_prob = precip_prob[i] if i < len(precip_prob) else 0
                            wind_mph = (wind_max[i] if i < len(wind_max) else 0) * 2.237

                            forecast_summary += f"{date_str}: {min_temp}-{max_temp}C {rain_prob}% rain {wind_mph:.0f}mph\n"

                        # Format result (concise for mesh network)
                        result = (
                            f"{location.title()}: {temp_current}C wind {wind_current:.0f}mph rain {precip_current}mm\n"
                            f"{forecast_summary.strip()}"
                        )

                        logger.info(
                            f"🌤️ TOOL RESULT: get_weather -> {len(result)} chars"
                        )
                        return result.strip()
            except Exception as http_err:
                logger.error(f"🌐 HTTP request failed: {http_err}")
                return "Weather service unavailable. Please try again later."

        except Exception as e:
            logger.error(f"Error getting weather: {e}")
            return "Weather information unavailable"
