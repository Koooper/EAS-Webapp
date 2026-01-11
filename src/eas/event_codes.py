"""
EAS Event codes per 47 CFR 11.31

Categories:
- national: Presidential/national emergency
- weather: NWS weather alerts
- civil: State/local civil emergencies
- test: Test alerts
"""

EVENT_CODES = {
    # National emergencies
    'EAN': {
        'name': 'Emergency Action Notification',
        'category': 'national',
        'description': 'National emergency, presidential message',
        'originator': 'PEP',
        'priority': 1
    },
    'EAT': {
        'name': 'Emergency Action Termination',
        'category': 'national',
        'description': 'Termination of EAN',
        'originator': 'PEP',
        'priority': 1
    },
    'NIC': {
        'name': 'National Information Center',
        'category': 'national',
        'description': 'National information statement',
        'originator': 'PEP',
        'priority': 2
    },

    # Severe weather - warnings (imminent threat)
    'TOR': {
        'name': 'Tornado Warning',
        'category': 'weather',
        'description': 'Tornado has been sighted or indicated by radar',
        'originator': 'WXR',
        'priority': 1
    },
    'SVR': {
        'name': 'Severe Thunderstorm Warning',
        'category': 'weather',
        'description': 'Severe thunderstorm with damaging winds/hail',
        'originator': 'WXR',
        'priority': 2
    },
    'FFW': {
        'name': 'Flash Flood Warning',
        'category': 'weather',
        'description': 'Flash flooding is imminent or occurring',
        'originator': 'WXR',
        'priority': 2
    },
    'SMW': {
        'name': 'Special Marine Warning',
        'category': 'weather',
        'description': 'Hazardous marine conditions',
        'originator': 'WXR',
        'priority': 3
    },
    'SVS': {
        'name': 'Severe Weather Statement',
        'category': 'weather',
        'description': 'Follow-up to severe weather warning',
        'originator': 'WXR',
        'priority': 3
    },
    'EWW': {
        'name': 'Extreme Wind Warning',
        'category': 'weather',
        'description': 'Extreme sustained winds of 115+ mph',
        'originator': 'WXR',
        'priority': 1
    },

    # Severe weather - watches (potential threat)
    'TOA': {
        'name': 'Tornado Watch',
        'category': 'weather',
        'description': 'Conditions favorable for tornadoes',
        'originator': 'WXR',
        'priority': 3
    },
    'SVA': {
        'name': 'Severe Thunderstorm Watch',
        'category': 'weather',
        'description': 'Conditions favorable for severe storms',
        'originator': 'WXR',
        'priority': 4
    },
    'FFA': {
        'name': 'Flash Flood Watch',
        'category': 'weather',
        'description': 'Conditions favorable for flash flooding',
        'originator': 'WXR',
        'priority': 4
    },

    # Flood warnings
    'FLW': {
        'name': 'Flood Warning',
        'category': 'weather',
        'description': 'Flooding is imminent or occurring',
        'originator': 'WXR',
        'priority': 3
    },
    'FLS': {
        'name': 'Flood Statement',
        'category': 'weather',
        'description': 'Follow-up to flood warning',
        'originator': 'WXR',
        'priority': 4
    },
    'FLA': {
        'name': 'Flood Watch',
        'category': 'weather',
        'description': 'Conditions favorable for flooding',
        'originator': 'WXR',
        'priority': 5
    },

    # Winter weather
    'WSW': {
        'name': 'Winter Storm Warning',
        'category': 'weather',
        'description': 'Significant winter weather expected',
        'originator': 'WXR',
        'priority': 3
    },
    'BZW': {
        'name': 'Blizzard Warning',
        'category': 'weather',
        'description': 'Blizzard conditions expected',
        'originator': 'WXR',
        'priority': 2
    },
    'WSA': {
        'name': 'Winter Storm Watch',
        'category': 'weather',
        'description': 'Potential for significant winter weather',
        'originator': 'WXR',
        'priority': 4
    },
    'WCW': {
        'name': 'Wind Chill Warning',
        'category': 'weather',
        'description': 'Dangerously cold wind chills',
        'originator': 'WXR',
        'priority': 3
    },
    'ICW': {
        'name': 'Ice Storm Warning',
        'category': 'weather',
        'description': 'Significant ice accumulation expected',
        'originator': 'WXR',
        'priority': 2
    },

    # Heat
    'EHW': {
        'name': 'Excessive Heat Warning',
        'category': 'weather',
        'description': 'Dangerously high temperatures',
        'originator': 'WXR',
        'priority': 2
    },
    'HWW': {
        'name': 'High Wind Warning',
        'category': 'weather',
        'description': 'High sustained winds expected',
        'originator': 'WXR',
        'priority': 3
    },

    # Tropical/Hurricane
    'HUW': {
        'name': 'Hurricane Warning',
        'category': 'weather',
        'description': 'Hurricane conditions expected within 36 hours',
        'originator': 'WXR',
        'priority': 1
    },
    'HUA': {
        'name': 'Hurricane Watch',
        'category': 'weather',
        'description': 'Hurricane conditions possible within 48 hours',
        'originator': 'WXR',
        'priority': 2
    },
    'HLS': {
        'name': 'Hurricane Statement',
        'category': 'weather',
        'description': 'Hurricane information statement',
        'originator': 'WXR',
        'priority': 3
    },
    'TRW': {
        'name': 'Tropical Storm Warning',
        'category': 'weather',
        'description': 'Tropical storm conditions expected',
        'originator': 'WXR',
        'priority': 2
    },
    'TRA': {
        'name': 'Tropical Storm Watch',
        'category': 'weather',
        'description': 'Tropical storm conditions possible',
        'originator': 'WXR',
        'priority': 3
    },

    # Tsunami
    'TSW': {
        'name': 'Tsunami Warning',
        'category': 'weather',
        'description': 'Tsunami expected, immediate action required',
        'originator': 'WXR',
        'priority': 1
    },
    'TSA': {
        'name': 'Tsunami Watch',
        'category': 'weather',
        'description': 'Tsunami possible, be alert',
        'originator': 'WXR',
        'priority': 2
    },

    # Fire
    'FRW': {
        'name': 'Fire Warning',
        'category': 'weather',
        'description': 'Wildfire threatening populated areas',
        'originator': 'WXR',
        'priority': 2
    },

    # Dust/Volcano
    'DSW': {
        'name': 'Dust Storm Warning',
        'category': 'weather',
        'description': 'Dust storm reducing visibility',
        'originator': 'WXR',
        'priority': 3
    },
    'VOW': {
        'name': 'Volcano Warning',
        'category': 'weather',
        'description': 'Volcanic activity threatening area',
        'originator': 'WXR',
        'priority': 1
    },

    # Civil emergencies
    'CDW': {
        'name': 'Civil Danger Warning',
        'category': 'civil',
        'description': 'Civil emergency in progress',
        'originator': 'CIV',
        'priority': 1
    },
    'CEM': {
        'name': 'Civil Emergency Message',
        'category': 'civil',
        'description': 'Civil emergency information',
        'originator': 'CIV',
        'priority': 2
    },
    'LAE': {
        'name': 'Local Area Emergency',
        'category': 'civil',
        'description': 'Emergency affecting local area',
        'originator': 'CIV',
        'priority': 2
    },
    'LEW': {
        'name': 'Law Enforcement Warning',
        'category': 'civil',
        'description': 'Law enforcement emergency',
        'originator': 'CIV',
        'priority': 1
    },
    'CAE': {
        'name': 'Child Abduction Emergency',
        'category': 'civil',
        'description': 'AMBER Alert',
        'originator': 'CIV',
        'priority': 1
    },
    'BLU': {
        'name': 'Blue Alert',
        'category': 'civil',
        'description': 'Law enforcement officer threat',
        'originator': 'CIV',
        'priority': 1
    },
    'SPW': {
        'name': 'Shelter in Place Warning',
        'category': 'civil',
        'description': 'Shelter in place required',
        'originator': 'CIV',
        'priority': 1
    },
    'EVA': {
        'name': 'Evacuation Immediate',
        'category': 'civil',
        'description': 'Immediate evacuation required',
        'originator': 'CIV',
        'priority': 1
    },

    # HAZMAT/Nuclear
    'NUW': {
        'name': 'Nuclear Power Plant Warning',
        'category': 'civil',
        'description': 'Nuclear power plant emergency',
        'originator': 'CIV',
        'priority': 1
    },
    'RHW': {
        'name': 'Radiological Hazard Warning',
        'category': 'civil',
        'description': 'Radiological hazard in area',
        'originator': 'CIV',
        'priority': 1
    },
    'HMW': {
        'name': 'Hazardous Materials Warning',
        'category': 'civil',
        'description': 'Hazardous materials release',
        'originator': 'CIV',
        'priority': 1
    },

    # Tests
    'RWT': {
        'name': 'Required Weekly Test',
        'category': 'test',
        'description': 'Weekly EAS equipment test',
        'originator': 'EAS',
        'priority': 10
    },
    'RMT': {
        'name': 'Required Monthly Test',
        'category': 'test',
        'description': 'Monthly EAS equipment test',
        'originator': 'EAS',
        'priority': 10
    },
    'NPT': {
        'name': 'National Periodic Test',
        'category': 'test',
        'description': 'National EAS test',
        'originator': 'PEP',
        'priority': 5
    },
    'DMO': {
        'name': 'Practice/Demo Warning',
        'category': 'test',
        'description': 'Practice or demonstration alert',
        'originator': 'EAS',
        'priority': 10
    },

    # Administrative
    'ADR': {
        'name': 'Administrative Message',
        'category': 'civil',
        'description': 'Administrative information',
        'originator': 'EAS',
        'priority': 8
    },
    'AVW': {
        'name': 'Avalanche Warning',
        'category': 'weather',
        'description': 'Avalanche expected or occurring',
        'originator': 'WXR',
        'priority': 2
    },
    'AVA': {
        'name': 'Avalanche Watch',
        'category': 'weather',
        'description': 'Conditions favorable for avalanche',
        'originator': 'WXR',
        'priority': 4
    },
}


def get_event_description(code: str) -> str:
    """Get human-readable name for an event code."""
    code = code.upper()
    if code in EVENT_CODES:
        return EVENT_CODES[code]['name']
    return f"Unknown event: {code}"


def get_events_by_category(category: str) -> dict:
    """Get all event codes for a category."""
    return {
        code: info for code, info in EVENT_CODES.items()
        if info['category'] == category
    }
