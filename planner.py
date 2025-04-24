import logging
import concurrent.futures
from providers.kcls import KCLSEventProvider
from providers.parentmap import ParentMapEventProvider

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
            if event.format != "Online":
                print(f"Location: {event.location} ({event.full_address if event.full_address else 'Incomplete address'})")
            else:
                print(f"Location: Online")

            if event.weather:
                print(f"Weather for {event.weather['datetime'].strftime('%Y-%m-%d %H:%M')}: {event.weather['summary']} (max temperature of {event.weather['temp_max']}°C, winds of {event.weather['max_wind_speed']} km/h, and {event.weather['precipitation_probability_text']})")
            else:
                print("Weather data not available.")
            
            print(f"Link: {event.link}")
            print(f"Description: {event.description}\n")


if __name__ == "__main__":
    main(logging.getLogger(__name__))