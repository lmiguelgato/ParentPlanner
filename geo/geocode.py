import re
import requests

def geocode_address(address):
    address = normalize_address(address)
    address = enrich_with_context(address)

    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': address,
        'format': 'json',
        'limit': 1
    }
    headers = {'User-Agent': 'ParentingPlannerBot/1.0'}

    response = requests.get(url, params=params, headers=headers)
    
    data = response.json()
    if data:
        return float(data[0]['lat']), float(data[0]['lon'])
    else:
        return None, None

def enrich_with_context(address):
    if "WA" not in address:
        return address + ", WA, USA"
    if "USA" not in address:
        return address + ", USA"
    return address

def normalize_address(address):
    ordinals = {
        "First": "1st", "Second": "2nd", "Third": "3rd", "Fourth": "4th",
        "Fifth": "5th", "Sixth": "6th", "Seventh": "7th", "Eighth": "8th", "Ninth": "9th", "Tenth": "10th"
    }
    for word, number in ordinals.items():
        address = re.sub(rf"\b{word}\b", number, address)

    address = address.replace("Ave.", "Ave").replace("St.", "St").replace("Blvd.", "Blvd")
    return address.strip()


# Example:
#lat, lon = geocode_address("Kirkland Urban, 425 Urban Plaza, Kirkland")
#print(lat, lon)
