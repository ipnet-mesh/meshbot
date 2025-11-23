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
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        forecast_days: int = 1,
    ) -> str:
        """Get weather forecast using Open-Meteo API.

        Uses coordinates from WEATHER_LATITUDE and WEATHER_LONGITUDE environment variables.
        Coordinates can be optionally overridden via parameters.

        Args:
            latitude: Latitude coordinate (default: from WEATHER_LATITUDE env var)
            longitude: Longitude coordinate (default: from WEATHER_LONGITUDE env var)
            forecast_days: Number of forecast days (default: 1)

        Returns:
            Concise weather summary with forecast
        """
        logger.info(
            f"🌤️ TOOL CALL: get_weather(lat={latitude}, lon={longitude}, days={forecast_days})"
        )
        try:
            import os

            # Check if aiohttp is available
            if not aiohttp:
                return "Weather service unavailable (aiohttp not installed)"

            # Get coordinates from parameters or environment variables
            if latitude is not None and longitude is not None:
                lat, lon = latitude, longitude
            else:
                # Get from environment variables (required)
                lat_env = os.getenv("WEATHER_LATITUDE")
                lon_env = os.getenv("WEATHER_LONGITUDE")

                if not lat_env or not lon_env:
                    return "Weather coordinates not configured. Set WEATHER_LATITUDE and WEATHER_LONGITUDE environment variables."

                try:
                    lat = float(lat_env)
                    lon = float(lon_env)
                except ValueError:
                    return "Invalid weather coordinates in environment variables. Must be valid numbers."

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
                            logger.error(
                                f"🌐 No current field in response: {data.keys()}"
                            )
                            return "Weather data unavailable"

                        current = data["current"]
                        temp_current = current.get("temperature_2m", "N/A")
                        wind_current = (
                            current.get("wind_speed_10m", 0) * 2.237
                        )  # Convert m/s to mph
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
                            f"Weather at ({lat:.2f}, {lon:.2f}): {temp_current}C wind {wind_current:.0f}mph rain {precip_current}mm\n"
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
            logger.info(f"Error getting weather: {e}")
            return "Weather information unavailable"
