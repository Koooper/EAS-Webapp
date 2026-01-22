"""
Batch file format parsers for CSV and JSON.
"""

import csv
import json
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from io import StringIO


@dataclass
class BatchAlert:
    """Represents a single alert in a batch."""
    originator: str
    event: str
    locations: List[str]
    duration_minutes: int
    callsign: str
    attention_duration: float = 8.0
    voice_text: Optional[str] = None
    voice_style: str = 'DEFAULT'

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API consumption."""
        return {
            'originator': self.originator,
            'event': self.event,
            'locations': self.locations,
            'duration': self.duration_minutes,
            'callsign': self.callsign,
            'attention_duration': self.attention_duration,
            'voice_text': self.voice_text,
            'voice': self.voice_style
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BatchAlert':
        """Create from dictionary."""
        # handle both 'duration' and 'duration_minutes' keys
        duration = data.get('duration_minutes', data.get('duration', 30))

        # handle locations as string (comma-separated) or list
        locations = data.get('locations', [])
        if isinstance(locations, str):
            locations = [loc.strip() for loc in locations.split(',')]

        return cls(
            originator=data['originator'],
            event=data['event'],
            locations=locations,
            duration_minutes=int(duration),
            callsign=data['callsign'],
            attention_duration=float(data.get('attention_duration', 8.0)),
            voice_text=data.get('voice_text'),
            voice_style=data.get('voice_style', data.get('voice', 'DEFAULT'))
        )


def parse_csv_batch(csv_content: str) -> List[BatchAlert]:
    """
    Parse CSV batch file.

    Expected columns:
        originator,event,locations,duration,callsign,attention_duration,voice_text,voice_style

    locations should be comma-separated FIPS codes (use quotes if containing commas)
    voice_text and voice_style are optional

    Example:
        WXR,TOR,"029095 029097",30,WXYZ/FM,8,,DEFAULT
        CIV,EAN,000000,60,KCIV/TV,25,This is a test,MALE
    """
    reader = csv.DictReader(StringIO(csv_content))
    alerts = []

    for row in reader:
        try:
            # parse locations (may be space or comma separated)
            locations_str = row.get('locations', '')
            locations = [loc.strip() for loc in locations_str.replace(',', ' ').split() if loc.strip()]

            alert = BatchAlert(
                originator=row['originator'].strip(),
                event=row['event'].strip(),
                locations=locations,
                duration_minutes=int(row.get('duration', row.get('duration_minutes', 30))),
                callsign=row['callsign'].strip(),
                attention_duration=float(row.get('attention_duration', 8.0)),
                voice_text=row.get('voice_text', '').strip() or None,
                voice_style=row.get('voice_style', row.get('voice', 'DEFAULT')).strip()
            )
            alerts.append(alert)
        except (KeyError, ValueError) as e:
            raise ValueError(f"Invalid CSV row: {row}. Error: {e}")

    if not alerts:
        raise ValueError("No valid alerts found in CSV")

    return alerts


def parse_json_batch(json_content: str) -> List[BatchAlert]:
    """
    Parse JSON batch file.

    Expected format:
    {
        "alerts": [
            {
                "originator": "WXR",
                "event": "TOR",
                "locations": ["029095", "029097"],
                "duration": 30,
                "callsign": "WXYZ/FM",
                "attention_duration": 8,
                "voice_text": null,
                "voice_style": "DEFAULT"
            },
            ...
        ]
    }

    Or as a simple array:
    [
        {...},
        {...}
    ]
    """
    data = json.loads(json_content)

    # handle both {"alerts": [...]} and [...] formats
    if isinstance(data, dict):
        if 'alerts' not in data:
            raise ValueError("JSON must contain 'alerts' key or be an array")
        alerts_data = data['alerts']
    elif isinstance(data, list):
        alerts_data = data
    else:
        raise ValueError("JSON must be an object with 'alerts' key or an array")

    alerts = []
    for item in alerts_data:
        try:
            alert = BatchAlert.from_dict(item)
            alerts.append(alert)
        except (KeyError, ValueError, TypeError) as e:
            raise ValueError(f"Invalid alert object: {item}. Error: {e}")

    if not alerts:
        raise ValueError("No valid alerts found in JSON")

    return alerts


def generate_csv_template() -> str:
    """Generate a CSV template file for batch import."""
    template = """originator,event,locations,duration,callsign,attention_duration,voice_text,voice_style
WXR,TOR,"029095 029097",30,KWNS/NWS,8,,DEFAULT
WXR,SVR,048001,15,WXYZ/FM,8,Severe thunderstorm warning for...,FEMALE
CIV,EVI,012345,60,KCIV/TV,10,,MALE
EAS,RWT,000000,15,TEST/FM,8,This is a test,DEFAULT"""
    return template


def generate_json_template() -> str:
    """Generate a JSON template file for batch import."""
    template = {
        "alerts": [
            {
                "originator": "WXR",
                "event": "TOR",
                "locations": ["029095", "029097"],
                "duration": 30,
                "callsign": "KWNS/NWS",
                "attention_duration": 8.0,
                "voice_text": None,
                "voice_style": "DEFAULT"
            },
            {
                "originator": "WXR",
                "event": "SVR",
                "locations": ["048001"],
                "duration": 15,
                "callsign": "WXYZ/FM",
                "attention_duration": 8.0,
                "voice_text": "Severe thunderstorm warning for...",
                "voice_style": "FEMALE"
            }
        ]
    }
    return json.dumps(template, indent=2)
