import re
import requests
from bs4 import BeautifulSoup

def extract_metadata(raw_html, title, link):
    # Parse HTML for metadata extraction
    soup = BeautifulSoup(raw_html, 'html.parser')
    
    # Clean title (remove leading number and period)
    cleaned_title = re.sub(r"^\d+\.\s*", "", title)
    
    # Find all the strong tags which contain our metadata labels
    strong_tags = soup.find_all('strong')
    
    date = cost = location = description = None
    
    for tag in strong_tags:
        label_text = tag.get_text().strip().lower()
        if 'date:' in label_text:
            # Get the text after this strong tag until the next <br>
            date_text = []
            next_elem = tag.next_sibling
            while next_elem and not (hasattr(next_elem, 'name') and next_elem.name == 'br'):
                if isinstance(next_elem, str):
                    date_text.append(next_elem)
                next_elem = next_elem.next_sibling if hasattr(next_elem, 'next_sibling') else None
            date = ''.join(date_text).strip()
            
        elif 'cost:' in label_text:
            # Get the text after this strong tag until the next <br>
            cost_text = []
            next_elem = tag.next_sibling
            while next_elem and not (hasattr(next_elem, 'name') and next_elem.name == 'br'):
                if isinstance(next_elem, str):
                    cost_text.append(next_elem)
                next_elem = next_elem.next_sibling if hasattr(next_elem, 'next_sibling') else None
            cost = ''.join(cost_text).strip()
            
        elif 'location:' in label_text:
            # Get the text after this strong tag until the next <br>
            location_text = []
            next_elem = tag.next_sibling
            while next_elem and not (hasattr(next_elem, 'name') and next_elem.name == 'br'):
                if isinstance(next_elem, str) or (hasattr(next_elem, 'name') and next_elem.name == 'a'):
                    if hasattr(next_elem, 'get_text'):
                        location_text.append(next_elem.get_text())
                    else:
                        location_text.append(str(next_elem))
                next_elem = next_elem.next_sibling if hasattr(next_elem, 'next_sibling') else None
            location = ''.join(location_text).strip()
    
    # Extract the description (all text after the last <br><br>)
    br_tags = soup.find_all('br')
    
    description = ""
    if len(br_tags) >= 4:  # We need at least 4 <br> tags to have two <br><br> pairs
        # The description starts after the last <br>
        last_br = br_tags[-1]
        
        # Get all content (text nodes and elements) after the last <br>
        for sibling in last_br.next_siblings:
            if isinstance(sibling, str):
                description += sibling
            elif hasattr(sibling, 'get_text'):
                description += sibling.get_text()
                
        description = description.strip()
    
    return {
        "title": cleaned_title,
        "link": link,
        "date": date,
        "cost": cost,
        "location": location,
        "description": description
    }

URL = "https://www.parentmap.com/article/the-weekender"
HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

response = requests.get(URL, headers=HEADERS)
soup = BeautifulSoup(response.content, "html.parser")

# Step 1: Find the main content div
content_div = soup.find("div", class_="field_content_sections")

if not content_div:
    print("⚠️ Could not find content section.")
else:
    print("✅ Content section found.")

    # Step 2: Extract all events (h3 + p combinations)
    events = []
    current_title = ""
    current_link = None

    for elem in content_div.find_all(["h3", "p"], recursive=True):
        if elem.name == "h3":
            # This is a new event title
            current_title = elem.get_text(strip=True)
            current_link = elem.find("a")["href"] if elem.find("a") else None
        elif elem.name == "p" and current_title:
            # This is the event description paragraph
            # Instead of extracting text, store the raw HTML
            raw_html = str(elem)
            events.append({
                "title": current_title,
                "link": current_link,
                "raw_html": raw_html
            })
            current_title = ""
            current_link = None
    
    # Process each event's raw HTML to extract structured data
    structured_events = [
        extract_metadata(event["raw_html"], event["title"], event["link"]) 
        for event in events
    ]
    
    # Filter out events with missing required fields
    filtered_events = [
        event for event in structured_events
        if event["date"] and event["cost"] and event["location"]
    ]

    # Preview result
    for i, e in enumerate(filtered_events, 1):
        print(f"\n--- Event #{i} ---")
        print("Title:", e["title"])
        print("Date:", e["date"])
        print("Cost:", e["cost"])
        print("Location:", e["location"])
        print("Link:", e["link"])
        print("Description:", e["description"])