"""
EAS Originator codes per 47 CFR 11.31
"""

ORIGINATOR_CODES = {
    'PEP': {
        'name': 'Primary Entry Point System',
        'description': 'Presidential-level alerts from FEMA IPAWS',
        'priority': 1
    },
    'CIV': {
        'name': 'Civil Authorities',
        'description': 'State and local government alerts',
        'priority': 2
    },
    'WXR': {
        'name': 'National Weather Service',
        'description': 'Weather-related warnings and watches',
        'priority': 3
    },
    'EAS': {
        'name': 'EAS Participant',
        'description': 'Broadcast station or cable system',
        'priority': 4
    }
}


def get_originator_description(code: str) -> str:
    """Get human-readable description of an originator code."""
    code = code.upper()
    if code in ORIGINATOR_CODES:
        return ORIGINATOR_CODES[code]['name']
    return f"Unknown originator: {code}"
