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


def get_weather_forecast(lat_lon_tuple, datetime_start=None, datetime_end=None):
    lat, lon = lat_lon_tuple
    if lat is None or lon is None:
        logger.warning("Cannot fetch weather without coordinates.")
        return None

    # Handle date/datetime for start
    if datetime_start is None:
        datetime_start = datetime.utcnow()
    
    # For API parameters, we need date strings
    if isinstance(datetime_start, datetime):
        start_date = datetime_start.strftime('%Y-%m-%d')
        start_hour = datetime_start.hour
    else:
        # Try to parse string date
        try:
            parsed_date = datetime.strptime(datetime_start, '%Y-%m-%d')
            start_date = datetime_start
            start_hour = 0  # Default to beginning of day
        except (ValueError, TypeError):
            # Try to parse datetime string
            try:
                parsed_date = datetime.strptime(datetime_start, '%Y-%m-%d %H:%M:%S')
                start_date = parsed_date.strftime('%Y-%m-%d')
                start_hour = parsed_date.hour
            except (ValueError, TypeError):
                # Fallback if parsing fails
                logger.warning("Could not parse datetime_start, using current time")
                now = datetime.utcnow()
                start_date = now.strftime('%Y-%m-%d')
                start_hour = now.hour
    
    # Handle date/datetime for end
    if datetime_end is None:
        # Default to start date + 1 day if not provided
        if isinstance(datetime_start, datetime):
            end_date = (datetime_start + timedelta(days=1)).strftime('%Y-%m-%d')
            end_hour = start_hour  # Same hour next day
        else:
            # Use the parsed start date
            try:
                end_date = (datetime.strptime(start_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
                end_hour = start_hour
            except (ValueError, TypeError):
                # Fallback if parsing fails
                logger.warning("Using default end date")
                now = datetime.utcnow()
                end_date = (now + timedelta(days=1)).strftime('%Y-%m-%d')
                end_hour = now.hour
    else:
        if isinstance(datetime_end, datetime):
            end_date = datetime_end.strftime('%Y-%m-%d')
            end_hour = datetime_end.hour
        else:
            try:
                parsed_date = datetime.strptime(datetime_end, '%Y-%m-%d')
                end_date = datetime_end
                end_hour = 23  # Default to end of day
            except (ValueError, TypeError):
                try:
                    parsed_date = datetime.strptime(datetime_end, '%Y-%m-%d %H:%M:%S')
                    end_date = parsed_date.strftime('%Y-%m-%d')
                    end_hour = parsed_date.hour
                except (ValueError, TypeError):
                    logger.warning("Could not parse datetime_end, using start date + 1 day")
                    end_date = (datetime.strptime(start_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
                    end_hour = start_hour

    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,precipitation_probability,weathercode,precipitation,windspeed_10m",
        "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,windspeed_10m_max",
        "timezone": "America/Los_Angeles",
        "start_date": start_date,
        "end_date": end_date
    }

    try:
        response = requests.get("https://api.open-meteo.com/v1/forecast", params=params)
        response.raise_for_status()
        data = response.json()

        # Return both daily summary and hourly data for the specified time window
        if "daily" in data and "hourly" in data:
            # Daily summary 
            daily_forecast = {
                "date": data["daily"]["time"][0],
                "summary": get_weather_description(data["daily"]["weathercode"][0]),
                "temp_max": data["daily"]["temperature_2m_max"][0],
                "temp_min": data["daily"]["temperature_2m_min"][0],
                "precipitation_mm": data["daily"]["precipitation_sum"][0],
                "precipitation_probability_text": f"{data['daily']['precipitation_probability_max'][0]}% chance of rain",
                "max_wind_speed": data["daily"]["windspeed_10m_max"][0]  # Add max wind speed to daily data
            }
            
            # Extract hourly data for the requested time window
            hourly_data = []
            
            # Calculate time indices
            start_time_str = f"{start_date}T{start_hour:02d}:00"
            if start_date == end_date:
                end_hour_adjusted = min(end_hour + 1, 24)
            else:
                end_hour_adjusted = 24  # If different days, go to end of start day
                
            # Filter hourly data to match our time window
            for i, time_str in enumerate(data["hourly"]["time"]):
                hour_datetime = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                if start_date in time_str and hour_datetime.hour >= start_hour and hour_datetime.hour < end_hour_adjusted:
                    hourly_data.append({
                        "time": time_str,
                        "temperature": data["hourly"]["temperature_2m"][i],
                        "weather": get_weather_description(data["hourly"]["weathercode"][i]),
                        "precipitation_prob": data["hourly"]["precipitation_probability"][i],
                        "precipitation_mm": data["hourly"]["precipitation"][i],
                        "wind_speed": data["hourly"]["windspeed_10m"][i]  # Add wind speed to hourly data
                    })
            
            # Return combined forecast
            forecast = {
                "daily": daily_forecast,
                "hourly": hourly_data
            }
            
            return forecast
        else:
            logger.error("Unexpected response structure from weather API.")
            return None

    except requests.exceptions.RequestException as e:
        logger.error(f"Weather API request failed: {e}")
        return None
