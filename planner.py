import logging
import concurrent.futures
from providers.kcls import KCLSEventProvider
from providers.parentmap import ParentMapEventProvider
from tinydb import TinyDB, Query
import os
import litellm
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(".env")

# Configure litellm to use a free model
# Using a free tier model like OpenAI's gpt-3.5-turbo via LiteLLM
litellm.set_verbose = False

def generate_event_suggestion(event, logger):
    """Generate suggestions for events based on title, location, description, and weather."""
    try:
        # Skip generating suggestions for online events with no weather data
        if event.format == "Online" and not event.weather:
            return "This is an online event you can attend from the comfort of your home."
        
        # Prepare prompt with event details
        weather_info = ""
        if event.weather:
            weather_info = f"Weather conditions: {event.weather['summary']}, max temp of {event.weather['temp_max']}°C, winds of {event.weather['max_wind_speed']} km/h, and {event.weather['precipitation_probability_text']}."
        
        location_info = f"Location: {event.location} ({event.full_address})" if event.format != "Online" else "Location: Online event"
        
        prompt = f"""
        I need a brief suggestion for a family event (2-3 sentences max):
        
        Event Title: {event.title}
        {location_info}
        Date: {event.date}
        Time: {event.time}
        {weather_info}
        
        Description: {event.description[:200]}...
        
        Generate a friendly, brief suggestion about attending this event. If it's outdoors and weather is bad (rainy, windy, etc.), suggest indoor alternatives or preparation. Keep it short and helpful.
        """
        
        # Use a free model through LiteLLM
        response = litellm.completion(
            model="gpt-3.5-turbo",  # Usually has a free tier or inexpensive option
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150
        )
        
        suggestion = response.choices[0].message.content.strip()
        logger.info(f"Generated suggestion for event: {event.title}")
        return suggestion
    
    except Exception as e:
        logger.error(f"Error generating suggestion for event {event.title}: {str(e)}")
        return "No suggestion available due to an error."

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
        # Generate suggestion for the event
        #logger.info(f"Generating suggestion for event: {event.title}")
        suggestion = "TODO" #generate_event_suggestion(event, logger)
        
        # Convert event to dictionary for storage
        event_dict = event.__dict__.copy()
        
        # Handle non-serializable objects
        if 'weather' in event_dict and event_dict['weather']:
            if 'datetime' in event_dict['weather']:
                event_dict['weather']['datetime'] = event_dict['weather']['datetime'].isoformat()
        
        # Add provider information and suggestion
        event_dict['provider'] = provider_name
        event_dict['suggestion'] = suggestion
        
        # Check if this event already exists (by title and date)
        existing = db.search((Event.title == event.title) & (Event.date == event.date))
        
        if not existing:
            # Store new event
            db.insert(event_dict)
            stored_count += 1
        else:
            # Update existing event with suggestion if it doesn't have one
            if not existing[0].get('suggestion'):
                db.update({'suggestion': suggestion}, (Event.title == event.title) & (Event.date == event.date))
                logger.info(f"Updated existing event with suggestion: {event.title}")
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
            print(f"Description: {event.description}")
            
            # Display the suggestion
            if hasattr(event, 'suggestion'):
                print(f"Suggestion: {event.suggestion}")
            print()
    
    logger.info(f"Database summary: Added {total_stored} new events, skipped {total_skipped} duplicates")
    print(f"\nDatabase summary: Added {total_stored} new events, skipped {total_skipped} duplicates")

if __name__ == "__main__":
    main(logging.getLogger(__name__))