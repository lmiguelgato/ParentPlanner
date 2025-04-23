import logging
import requests
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def get_weather_description(weather_code):
    weather_codes = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        56: "Light freezing drizzle",
        57: "Dense freezing drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        66: "Light freezing rain",
        67: "Heavy freezing rain",
        71: "Slight snow fall",
        73: "Moderate snow fall",
        75: "Heavy snow fall",
        77: "Snow grains",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        85: "Slight snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail"
    }
    
    return weather_codes.get(weather_code, "Unknown weather code")


def get_weather_forecast(lat_lon_tuple):
    lat, lon = lat_lon_tuple
    if lat is None or lon is None:
        logger.warning("Cannot fetch weather without coordinates.")
        return None

    tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime('%Y-%m-%d')

    params = {
        "latitude": lat,
        "longitude": lon,
        'hourly': "precipitation_probability,weathercode",
        "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max",
        "timezone": "America/Los_Angeles",
        "start_date": tomorrow,
        "end_date": tomorrow
    }

    try:
        response = requests.get("https://api.open-meteo.com/v1/forecast", params=params)
        response.raise_for_status()
        data = response.json()

        if "daily" in data:
            forecast = {
                "date": data["daily"]["time"][0],
                #"summary_code": data["daily"]["weathercode"][0],
                "summary": get_weather_description(data["daily"]["weathercode"][0]),
                "temp_max": data["daily"]["temperature_2m_max"][0],
                "temp_min": data["daily"]["temperature_2m_min"][0],
                "precipitation_mm": data["daily"]["precipitation_sum"][0],
                "precipitation_probability_text": f"{data['daily']['precipitation_probability_max'][0]}% chance of rain",
            }
            return forecast
        else:
            logger.error("Unexpected response structure from weather API.")
            return None

    except requests.exceptions.RequestException as e:
        logger.error(f"Weather API request failed: {e}")
        return None
