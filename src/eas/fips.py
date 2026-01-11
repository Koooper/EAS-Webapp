"""
FIPS location codes for EAS

SAME location code format: PSSCCC
- P: Geographic subdivision (0 = entire county, 1-9 = subdivisions)
- SS: State code (01-95)
- CCC: County code (000 = entire state, 001-999 = counties)

Special codes:
- 000000: United States (all states)
"""

# State FIPS codes per ANSI INCITS 38
STATE_CODES = {
    '00': 'United States',
    '01': 'Alabama',
    '02': 'Alaska',
    '04': 'Arizona',
    '05': 'Arkansas',
    '06': 'California',
    '08': 'Colorado',
    '09': 'Connecticut',
    '10': 'Delaware',
    '11': 'District of Columbia',
    '12': 'Florida',
    '13': 'Georgia',
    '15': 'Hawaii',
    '16': 'Idaho',
    '17': 'Illinois',
    '18': 'Indiana',
    '19': 'Iowa',
    '20': 'Kansas',
    '21': 'Kentucky',
    '22': 'Louisiana',
    '23': 'Maine',
    '24': 'Maryland',
    '25': 'Massachusetts',
    '26': 'Michigan',
    '27': 'Minnesota',
    '28': 'Mississippi',
    '29': 'Missouri',
    '30': 'Montana',
    '31': 'Nebraska',
    '32': 'Nevada',
    '33': 'New Hampshire',
    '34': 'New Jersey',
    '35': 'New Mexico',
    '36': 'New York',
    '37': 'North Carolina',
    '38': 'North Dakota',
    '39': 'Ohio',
    '40': 'Oklahoma',
    '41': 'Oregon',
    '42': 'Pennsylvania',
    '44': 'Rhode Island',
    '45': 'South Carolina',
    '46': 'South Dakota',
    '47': 'Tennessee',
    '48': 'Texas',
    '49': 'Utah',
    '50': 'Vermont',
    '51': 'Virginia',
    '53': 'Washington',
    '54': 'West Virginia',
    '55': 'Wisconsin',
    '56': 'Wyoming',
    # Territories
    '60': 'American Samoa',
    '66': 'Guam',
    '69': 'Northern Mariana Islands',
    '72': 'Puerto Rico',
    '78': 'Virgin Islands',
    # Marine areas (special NWS codes)
    '91': 'Lake Superior',
    '92': 'Lake Michigan',
    '93': 'Lake Huron',
    '94': 'Lake St. Clair',
    '95': 'Lake Erie',
}

# Subdivision descriptions
SUBDIVISION_CODES = {
    '0': 'Entire area',
    '1': 'Northwest',
    '2': 'North',
    '3': 'Northeast',
    '4': 'West',
    '5': 'Central',
    '6': 'East',
    '7': 'Southwest',
    '8': 'South',
    '9': 'Southeast',
}


def parse_location_code(code: str) -> dict:
    """
    Parse a 6-digit SAME location code.

    Args:
        code: 6-digit FIPS location code

    Returns:
        Dict with subdivision, state, county components
    """
    if len(code) != 6 or not code.isdigit():
        raise ValueError(f"Invalid location code: {code}")

    return {
        'subdivision': code[0],
        'state': code[1:3],
        'county': code[3:6],
        'raw': code
    }


def get_state_name(state_code: str) -> str:
    """Get state name from 2-digit state code."""
    return STATE_CODES.get(state_code, f"Unknown state: {state_code}")


def get_county_name(state_code: str, county_code: str) -> str:
    """
    Get county name.

    Note: Full county database not included - would need external data source.
    Returns generic description for now.
    """
    if county_code == '000':
        return "Entire state"
    return f"County {county_code}"


def format_location_code(code: str) -> str:
    """
    Format a location code as human-readable string.

    Args:
        code: 6-digit FIPS location code

    Returns:
        Human-readable location description
    """
    parsed = parse_location_code(code)

    subdivision = SUBDIVISION_CODES.get(parsed['subdivision'], '')
    state = get_state_name(parsed['state'])
    county = get_county_name(parsed['state'], parsed['county'])

    if parsed['county'] == '000':
        if parsed['subdivision'] == '0':
            return f"{state}"
        else:
            return f"{subdivision} {state}"
    else:
        if parsed['subdivision'] == '0':
            return f"{county}, {state}"
        else:
            return f"{subdivision} {county}, {state}"


def build_location_code(state: str, county: str = '000', subdivision: str = '0') -> str:
    """
    Build a 6-digit SAME location code.

    Args:
        state: 2-digit state code
        county: 3-digit county code (000 for entire state)
        subdivision: 1-digit subdivision code (0 for entire area)

    Returns:
        6-digit SAME location code
    """
    return f"{subdivision}{state}{county}"
