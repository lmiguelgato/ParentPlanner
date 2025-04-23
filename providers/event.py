from geo.geocode import geocode_address
from weather.weather_forecast import get_weather_forecast


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
        self.full_address, self.lat, self.lon = self.get_full_address()
        self.weather = self.get_weather_forecast()

    def __repr__(self):
        return f"{self.provider} event: {self.title} on {self.date} at {self.location}"

    def get_full_address(self):
        if self.format != "Online":
            complete_address, lat, lon = geocode_address(self.location)
            return complete_address, lat, lon
        return None, None, None
    
    def get_weather_forecast(self):
        if self.format != "Online":
            if self.lat and self.lon:
                weather_forecast = get_weather_forecast((self.lat, self.lon))
                if weather_forecast:
                    return {
                        'summary': weather_forecast['summary'],
                        'temp_max': weather_forecast['temp_max'],
                        'temp_min': weather_forecast['temp_min'],
                        'precipitation_mm': weather_forecast['precipitation_mm'],
                        'precipitation_probability_text': weather_forecast['precipitation_probability_text']
                    }
        return None

class EventProvider:
    def __init__(self):
        self.events = []

    def get_event(self):
        pass
