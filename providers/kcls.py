import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import logging
from .event import Event, EventProvider

logger = logging.getLogger(__name__)

class KCLSEventProvider(EventProvider):
    def __init__(self):
        super().__init__()

    def download_events(self):
        logger.info("Downloading events from KCLS...")
        raw_events = asyncio.run(self.__scrape_upcoming_events())
        for event in raw_events:
            event = Event(
                provider='KCLS',
                title=event['title'],
                status=event['status'],
                link=event['link'],
                date=event['date'],
                time=event['time'],
                cost=event['cost'],
                location=event['location'],
                description=event['description'],
                format=event['format']
            )
            self.events.append(event)
        
        logger.info(f"{len(self.events)} events downloaded from KCLS.")

    async def __scrape_upcoming_events(self):
        async with async_playwright() as p:
            logger.info("Launching browser...")
            browser = await p.chromium.launch(headless=True)
            logger.info("Opening new page...")
            page = await browser.new_page()
            # Spanish/English events for kids 8 and under:
            logger.info("Checking for Spanish/English events for kids 8 and under...")
            await page.goto('https://kcls.bibliocommons.com/v2/events?audiences=572b6201717c23254b000013%2C572b6201717c23254b000014%2C572b6201717c23254b000012&languages=5654e8049967fa8d27000012%2C5654e8049967fa8d27000014', wait_until='networkidle')
            await page.wait_for_load_state('networkidle')

            logger.info("Waiting for page to load...")
            content = await page.content()
            logger.info("Page loaded. Parsing content...")
            soup = BeautifulSoup(content, 'html.parser')

            events = []

            # Target div elements with class 'event-details'
            event_divs = soup.find_all('div', class_='event-details')
            if not event_divs:
                logger.warning("No event divs found. Check the page structure.")
                await browser.close()
                return []
            
            logger.info(f"Found {len(event_divs)} event divs.")

            for event_div in event_divs:
                # Extract title
                title_tag = event_div.find('h3', class_='cp-heading')
                title = title_tag.find('a', class_='cp-link').get_text(strip=True) if title_tag and title_tag.find('a', class_='cp-link') else ''
                
                # Extract status
                status_badge = title_tag.find('span', class_='event-badge')
                status = 'Confirmed'  # Default status
                if status_badge and status_badge.find('div', class_='cp-badge'):
                    status = status_badge.find('div', class_='cp-badge').get_text(strip=True)
                
                # Extract link
                link_tag = event_div.find('a', class_='cp-link', attrs={'data-key': 'event-link'})
                link = link_tag.get('href') if link_tag else ''
                
                # Extract date and time
                date_div = event_div.find('div', class_='cp-event-date-time')
                date = ''
                time = ''
                if date_div:
                    # Check for "All day" events first
                    date_text = date_div.get_text(strip=True)
                    if 'All day' in date_text:
                        time = 'All day'
                        
                    # Try to get the more detailed date from the screen reader message
                    date_screen_reader = date_div.find_all('span', class_='cp-screen-reader-message')
                    if date_screen_reader and len(date_screen_reader) >= 1:
                        date = date_screen_reader[0].get_text(strip=True)
                        # Remove prefix if present
                        date = date.replace('on ', '').replace('from ', '')
                        
                        # Check if there's a time component (usually the second screen reader message)
                        if len(date_screen_reader) >= 2 and not time:  # Only set if not already "All day"
                            time_text = date_screen_reader[1].get_text(strip=True)
                            if 'am' in time_text.lower() or 'pm' in time_text.lower():
                                time = time_text
                    else:
                        # Fallback to the visible date
                        date_parts = date_text.split(', ')
                        if len(date_parts) > 1:
                            date = date_parts[1].split(', ')[0]  # Get just the date part
                            
                            # Try to extract time from visible text if not already "All day"
                            if not time:
                                time_spans = date_div.find_all('span', attrs={'aria-hidden': 'true'})
                                for span in time_spans:
                                    span_text = span.get_text(strip=True)
                                    if 'am' in span_text.lower() or 'pm' in span_text.lower():
                                        time = span_text
                
                # Extract location
                location_tag = event_div.find('a', attrs={'data-key': 'event-location-link'})
                location = location_tag.find('span', attrs={'aria-hidden': 'true'}).get_text(strip=True) if location_tag else ''
                
                # Determine if event is online or onsite
                event_type = 'Onsite'
                online_div = event_div.find('div', class_='cp-event-location')
                if online_div and online_div.find('span', string='Online event'):
                    event_type = 'Online'
                
                # Extract description
                desc_div = event_div.find('div', class_='cp-event-description')
                description = ''
                if desc_div and desc_div.find('p'):
                    # Get text from all paragraphs in the description
                    paragraphs = desc_div.find_all('p')
                    description = ' '.join([p.get_text(strip=True) for p in paragraphs])
                
                raw_event = {
                    'title': title,
                    'status': status,
                    'link': link,
                    'date': date,
                    'time': time,
                    'cost': 'Free', # Assuming all KCLS events are free
                    'location': f"{location} Library" if event_type == 'Onsite' else 'Online',
                    'description': description,
                    'format': event_type
                }

                events.append(raw_event)
                logger.info(f"Event found: {title} - {date} - {time} - {location}")

            logger.info(f"Total events found: {len(events)}")
            # Close the browser
            logger.info("Closing browser...")
            await browser.close()
            logger.info("Browser closed.")
            return events
