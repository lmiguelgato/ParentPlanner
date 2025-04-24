import logging
import concurrent.futures
from providers.kcls import KCLSEventProvider
from providers.parentmap import ParentMapEventProvider
from tinydb import TinyDB, Query
import os

logging.basicConfig(
    filename='planner.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def store_events_in_db(provider_name, events, logger):
    """Store events in TinyDB, skipping duplicates."""
    # Ensure db directory exists
    os.makedirs('data', exist_ok=True)
    
    # Open or create the database
    db = TinyDB('data/events.json')
    Event = Query()
    
    stored_count = 0
    skipped_count = 0
    
    for event in events:
        # Convert event to dictionary for storage
        event_dict = event.__dict__.copy()
        
        # Handle non-serializable objects
        if 'weather' in event_dict and event_dict['weather']:
            if 'datetime' in event_dict['weather']:
                event_dict['weather']['datetime'] = event_dict['weather']['datetime'].isoformat()
        
        # Add provider information
        event_dict['provider'] = provider_name
        
        # Check if this event already exists (by title and date)
        existing = db.search((Event.title == event.title) & (Event.date == event.date))
        
        if not existing:
            # Store new event
            db.insert(event_dict)
            stored_count += 1
        else:
            skipped_count += 1
    
    logger.info(f"Provider {provider_name}: Stored {stored_count} new events, skipped {skipped_count} duplicates")
    return stored_count, skipped_count

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

    # Store events in database
    total_stored = 0
    total_skipped = 0
    
    for provider, events in provider_events.items():
        stored, skipped = store_events_in_db(provider, events, logger)
        total_stored += stored
        total_skipped += skipped
        
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
                print(f"Weather for {event.weather['datetime']}: {event.weather['summary']} (max temperature of {event.weather['temp_max']}°C, winds of {event.weather['max_wind_speed']} km/h, and {event.weather['precipitation_probability_text']})")
            else:
                print("Weather data not available.")
            
            print(f"Link: {event.link}")
            print(f"Description: {event.description}\n")
    
    logger.info(f"Database summary: Added {total_stored} new events, skipped {total_skipped} duplicates")
    print(f"\nDatabase summary: Added {total_stored} new events, skipped {total_skipped} duplicates")


if __name__ == "__main__":
    main(logging.getLogger(__name__))