import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

async def scrape_kcls_events():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        # Spanish/English events for kids 8 and under:
        await page.goto('https://kcls.bibliocommons.com/v2/events?audiences=572b6201717c23254b000013%2C572b6201717c23254b000014%2C572b6201717c23254b000012&languages=5654e8049967fa8d27000012%2C5654e8049967fa8d27000014', wait_until='networkidle')
        await page.wait_for_load_state('networkidle')

        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')

        events = []

        # Target div elements with class 'event-details'
        event_divs = soup.find_all('div', class_='event-details')

        for event_div in event_divs:
            # Extract title
            title_tag = event_div.find('h3', class_='cp-heading')
            title = title_tag.find('a', class_='cp-link').get_text(strip=True) if title_tag and title_tag.find('a', class_='cp-link') else ''
            
            # Extract status
            status_badge = title_tag.find('span', class_='event-badge')
            status = ''
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
            
            # Extract description
            desc_div = event_div.find('div', class_='cp-event-description')
            description = ''
            if desc_div and desc_div.find('p'):
                # Get text from all paragraphs in the description
                paragraphs = desc_div.find_all('p')
                description = ' '.join([p.get_text(strip=True) for p in paragraphs])
            
            events.append({
                'title': title,
                'status': status,
                'link': link,
                'date': date,
                'time': time,
                'cost': 'Free', # Assuming all KCLS events are free
                'location': f"{location} Library",
                'description': description
            })

        await browser.close()
        return events

# Example usage
if __name__ == "__main__":
    events = asyncio.run(scrape_kcls_events())
    for event in events:
        print(f"Title: {event['title']}")
        if event['status']:
            print(f"Status: {event['status']}")
        print(f"Date: {event['date']}")
        if event['time']:
            print(f"Time: {event['time']}")
        print(f"Cost: {event['cost']}")
        print(f"Location: {event['location']}")
        print(f"Link: {event['link']}")
        print(f"Description: {event['description']}\n")