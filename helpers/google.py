import datetime
import logging
from urllib.parse import quote
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_LOCATION = 'Washington state, United States'

def get_event_location(event: Dict[str, Any]) -> str:
    """Extract the location from the event data."""
    if 'is_estimated_address' in event and not bool(event['is_estimated_address']) and 'full_address' in event and event['full_address']:
        return event['full_address']
    elif 'is_estimated_address' in event and bool(event['is_estimated_address']) and 'location' in event and event['location']:
        return event['location']
    return DEFAULT_LOCATION

def create_google_maps_link(location: str) -> str:
    """Create a Google Maps link for the given location."""
    return f"https://maps.google.com/?daddr={quote(location)}"

def parse_time(time_str: str) -> Optional[str]:
    """Parse time string into Google Calendar format."""
    try:
        time_parts = time_str.split(':')
        if len(time_parts) < 2:
            return None
            
        hour = int(time_parts[0])
        minute = int(time_parts[1].split()[0])
        is_pm = 'PM' in time_str.upper()
        
        # Convert to 24-hour format
        if is_pm and hour < 12:
            hour += 12
        elif not is_pm and hour == 12:
            hour = 0
            
        return f"T{hour:02d}{minute:02d}00"
    except Exception:
        return None

def parse_event_date(event_date: str, event_time: Optional[str] = None) -> dict:
    """Parse event date and time for calendar formatting."""
    try:
        date_parts = event_date.replace(',', '').split()
        if len(date_parts) < 2:
            return {}
            
        month_name = date_parts[1]
        day = date_parts[2] if len(date_parts) > 2 else '1'
        
        # Convert month name to number
        month_map = {
            'January': 1, 'February': 2, 'March': 3, 'April': 4,
            'May': 5, 'June': 6, 'July': 7, 'August': 8,
            'September': 9, 'October': 10, 'November': 11, 'December': 12
        }
        month_num = month_map.get(month_name, 1)
        
        # Use current year
        current_year = datetime.datetime.now().year
        
        # Format date
        date_str = f"{current_year}{month_num:02d}{int(day):02d}"
        
        result = {
            'start_date': date_str,
            'end_date': date_str
        }
        
        # Add time if available
        if event_time:
            time_parts = event_time.split(' - ')
            start_time = parse_time(time_parts[0])
            
            if start_time:
                result['start_date'] += start_time
                
                # Try to get end time
                if len(time_parts) > 1:
                    end_time = parse_time(time_parts[1])
                    if end_time:
                        result['end_date'] += end_time
                    else:
                        result['end_date'] += start_time  # Default to same as start time
                else:
                    result['end_date'] += start_time  # Default to same as start time
        
        return result
    except Exception as e:
        logger.error(f"Error parsing event date: {str(e)}")
        return {}

def create_google_calendar_link(event: Dict[str, Any]) -> str:
    """Create a Google Calendar link for the event."""
    title = quote(event['title'])
    location = quote(get_event_location(event))
    description = quote(event.get('description', ''))
    
    date_info = parse_event_date(event['date'], event.get('time', ''))
    if not date_info:
        return ""
    
    return (f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={title}"
            f"&dates={date_info['start_date']}/{date_info['end_date']}"
            f"&details={description}&location={location}")