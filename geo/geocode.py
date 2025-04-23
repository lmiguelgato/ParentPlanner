import re
import requests

def reverse_geocode(lat, lon):
    if lat is None or lon is None:
        return False

    # request the reverse geocode from Nominatim
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {
        'lat': lat,
        'lon': lon,
        'format': 'json',
        'addressdetails': 1
    }
    headers = {'User-Agent': 'ParentingPlannerBot/1.0'}
    response = requests.get(url, params=params, headers=headers)
    data = response.json()
    if data:
        address = data.get('address', {})
        state = address.get('state', '')
        country = address.get('country', '')
        return address, state, country
    
    return None, None, None
    

def is_valid_address(address):
    if not address or not isinstance(address, str) or len(address) < 10:
        return False
    return True

def geocode_address(address):
    if not is_valid_address(address):
        return None, None, None

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
        complete_address = data[0].get('display_name', '')

        if (", United States" not in complete_address) or (", Washington," not in complete_address) or (", District of Columbia" in complete_address):
            return None, None, None
        else:
            return complete_address, float(data[0]['lat']), float(data[0]['lon'])
    
    return None, None, None

def enrich_with_context(address):
    if ("WA" not in address) and ("Washington" not in address):
        return address + ", Washington, United States"
    if ("USA" not in address) and ("United States" not in address):
        return address + ", United States"
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
