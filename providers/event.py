from datetime import datetime, timedelta
import logging
from geo.geocode import geocode_address
from weather.weather_forecast import get_weather_forecast

logger = logging.getLogger(__name__)

class Event:
    def __init__(self, title, link, date, cost, location, description, status="Confirmed", time=None, provider=None, format="Onsite"):
        self.title = title
        self.link = link
        self.date = date
        self.cost = cost
        self.location = location
        self.description = description
        self.status = status
        self.time = time
        self.provider = provider
        self.format = format
        self.full_address, self.lat, self.lon, self.is_estimated_address = self.get_full_address()
        self.weather = self.weather_forecast()

    def __repr__(self):
        return f"{self.provider} event: {self.title} on {self.date} at {self.location}"

    def get_full_address(self):
        if self.format != "Online":
            return geocode_address(self.location)
        return None, None, None, False
    
    def weather_forecast(self):
        if self.format != "Online":
            if self.lat and self.lon:
                # Create a proper datetime object from date and time
                try:
                    # Get forecast for the event
                    event_datetime = datetime.utcnow()
                    # Estimate event duration - default to 2 hours
                    event_end = event_datetime + timedelta(hours=2)
                    weather_forecast = get_weather_forecast((self.lat, self.lon), event_datetime, event_end)
                    
                    if weather_forecast:
                        # If we have hourly data for the specific time, include it
                        hourly_weather = None
                        if 'hourly' in weather_forecast and weather_forecast['hourly']:
                            for hour_data in weather_forecast['hourly']:
                                hour_time = datetime.fromisoformat(hour_data['time'].replace('Z', '+00:00'))
                                if hour_time.hour == event_datetime.hour:
                                    hourly_weather = hour_data
                                    break
                        
                        # Convert UTC to Pacific time (PST/PDT)
                        # Pacific time is UTC-8 in standard time, UTC-7 in daylight saving time
                        # Check if we're in daylight saving time
                        is_dst = self._is_daylight_saving(event_datetime)
                        pacific_datetime = event_datetime - timedelta(hours=7 if is_dst else 8)
                        
                        return {
                            'datetime': pacific_datetime,
                            'summary': weather_forecast['daily']['summary'],
                            'temp_max': weather_forecast['daily']['temp_max'],
                            'temp_min': weather_forecast['daily']['temp_min'],
                            'max_wind_speed': weather_forecast['daily']['max_wind_speed'],
                            'precipitation_mm': weather_forecast['daily']['precipitation_mm'],
                            'precipitation_probability_text': weather_forecast['daily']['precipitation_probability_text'],
                            'hourly': hourly_weather  # This will be None if no specific hourly data found
                        }
                except Exception as e:
                    logger.error(f"Error getting weather forecast: {e}")
        return None

    def _is_daylight_saving(self, dt):
        """Simple helper method to determine if a date is in daylight saving time in US Pacific timezone."""
        # Basic rules for US Pacific DST:
        # Starts: Second Sunday in March
        # Ends: First Sunday in November
        year = dt.year
        
        # Calculate DST start for the year
        # 2nd Sunday in March
        march_date = datetime(year, 3, 1)
        # Find the first Sunday
        days_to_add = (6 - march_date.weekday()) % 7
        first_sunday = march_date + timedelta(days=days_to_add)
        # Second Sunday
        dst_start = first_sunday + timedelta(days=7)
        dst_start = dst_start.replace(hour=2)  # 2:00 AM
        
        # Calculate DST end for the year
        # 1st Sunday in November
        november_date = datetime(year, 11, 1)
        days_to_add = (6 - november_date.weekday()) % 7
        dst_end = november_date + timedelta(days=days_to_add)
        dst_end = dst_end.replace(hour=2)  # 2:00 AM
        
        return dst_start <= dt < dst_end

class EventProvider:
    def __init__(self):
        self.events = []

    def download_events(self):
        pass
