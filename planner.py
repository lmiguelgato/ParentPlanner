import logging
import concurrent.futures
from providers.kcls import KCLSEventProvider
from providers.parentmap import ParentMapEventProvider
from geo.geocode import geocode_address
from weather.weather_forecast import get_weather_forecast

logging.basicConfig(
    filename='planner.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main(logger):
    logger.info("Fetching events from providers")

    kcls = KCLSEventProvider()
    parentmap = ParentMapEventProvider()
    
    # Run downloads concurrently using ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Submit both download tasks
        kcls_future = executor.submit(kcls.download_events)
        parentmap_future = executor.submit(parentmap.download_events)
        
        # Wait for both to complete
        concurrent.futures.wait([kcls_future, parentmap_future])
    
    provider_events = {
        "KCLS": kcls.events,
        "ParentMap": parentmap.events
    }

    for provider, events in provider_events.items():
        print(f"Provider: {provider}")
        for event in events:
            print(f"Title: {event.title}")
            print(f"Status: {event.status}")
            print(f"Date: {event.date}")
            print(f"Time: {event.time}")
            print(f"Cost: {event.cost}")
            if event.type != "Online":
                complete_address, lat, lon = geocode_address(event.location)
                print(f"Location: {event.location} ({complete_address if complete_address else 'Incomplete address'})")

                if complete_address:
                    weather_forecast = get_weather_forecast((lat, lon))
                    if weather_forecast:
                        print(f"Weather: {weather_forecast['summary']}")
                        print(f"Max Temp: {weather_forecast['temp_max']}°C")
                        print(f"Min Temp: {weather_forecast['temp_min']}°C")
                        print(f"Precipitation: {weather_forecast['precipitation_mm']} mm")
                        print(f"Chance of Rain: {weather_forecast['precipitation_probability_text']}")
                    else:
                        print("⚠️ Weather data not available.")
            else:
                print(f"Location: Online")
            print(f"Link: {event.link}")
            print(f"Description: {event.description}\n")


if __name__ == "__main__":
    main(logging.getLogger(__name__))