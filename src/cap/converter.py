"""
CAP <-> SAME Converter

Bidirectional conversion between CAP alerts and SAME headers.
"""

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Optional, List, Dict

from .parser import (
    CAPAlert, CAPInfo, CAPArea,
    CAPStatus, CAPMsgType, CAPScope,
    CAPCategory, CAPUrgency, CAPSeverity, CAPCertainty
)
from ..same.message import SAMEMessage
from ..eas.event_codes import EVENT_CODES


# SAME event code to CAP event mapping
SAME_TO_CAP_EVENT = {
    'TOR': ('Tornado Warning', CAPCategory.MET, CAPSeverity.EXTREME),
    'SVR': ('Severe Thunderstorm Warning', CAPCategory.MET, CAPSeverity.SEVERE),
    'FFW': ('Flash Flood Warning', CAPCategory.MET, CAPSeverity.SEVERE),
    'FLW': ('Flood Warning', CAPCategory.MET, CAPSeverity.MODERATE),
    'TSW': ('Tsunami Warning', CAPCategory.GEO, CAPSeverity.EXTREME),
    'EWW': ('Extreme Wind Warning', CAPCategory.MET, CAPSeverity.EXTREME),
    'HUW': ('Hurricane Warning', CAPCategory.MET, CAPSeverity.EXTREME),
    'TRW': ('Tropical Storm Warning', CAPCategory.MET, CAPSeverity.SEVERE),
    'BZW': ('Blizzard Warning', CAPCategory.MET, CAPSeverity.SEVERE),
    'WSW': ('Winter Storm Warning', CAPCategory.MET, CAPSeverity.MODERATE),
    'ICW': ('Ice Storm Warning', CAPCategory.MET, CAPSeverity.SEVERE),
    'EHW': ('Excessive Heat Warning', CAPCategory.MET, CAPSeverity.SEVERE),
    'HWW': ('High Wind Warning', CAPCategory.MET, CAPSeverity.MODERATE),
    'FRW': ('Fire Warning', CAPCategory.FIRE, CAPSeverity.SEVERE),
    'VOW': ('Volcano Warning', CAPCategory.GEO, CAPSeverity.EXTREME),
    'EAN': ('Emergency Action Notification', CAPCategory.SAFETY, CAPSeverity.EXTREME),
    'CDW': ('Civil Danger Warning', CAPCategory.SAFETY, CAPSeverity.EXTREME),
    'CEM': ('Civil Emergency Message', CAPCategory.SAFETY, CAPSeverity.SEVERE),
    'CAE': ('Child Abduction Emergency', CAPCategory.SAFETY, CAPSeverity.SEVERE),
    'LEW': ('Law Enforcement Warning', CAPCategory.SECURITY, CAPSeverity.SEVERE),
    'BLU': ('Blue Alert', CAPCategory.SECURITY, CAPSeverity.SEVERE),
    'SPW': ('Shelter in Place Warning', CAPCategory.SAFETY, CAPSeverity.SEVERE),
    'EVA': ('Evacuation Immediate', CAPCategory.SAFETY, CAPSeverity.EXTREME),
    'NUW': ('Nuclear Power Plant Warning', CAPCategory.CBRNE, CAPSeverity.EXTREME),
    'RHW': ('Radiological Hazard Warning', CAPCategory.CBRNE, CAPSeverity.EXTREME),
    'HMW': ('Hazardous Materials Warning', CAPCategory.CBRNE, CAPSeverity.SEVERE),
    'RWT': ('Required Weekly Test', CAPCategory.OTHER, CAPSeverity.MINOR),
    'RMT': ('Required Monthly Test', CAPCategory.OTHER, CAPSeverity.MINOR),
    'NPT': ('National Periodic Test', CAPCategory.OTHER, CAPSeverity.MINOR),
    'DMO': ('Practice/Demo Warning', CAPCategory.OTHER, CAPSeverity.MINOR),
}

# CAP event to SAME code mapping (reverse lookup)
CAP_TO_SAME_EVENT = {
    'tornado warning': 'TOR',
    'severe thunderstorm warning': 'SVR',
    'flash flood warning': 'FFW',
    'flood warning': 'FLW',
    'tsunami warning': 'TSW',
    'extreme wind warning': 'EWW',
    'hurricane warning': 'HUW',
    'tropical storm warning': 'TRW',
    'blizzard warning': 'BZW',
    'winter storm warning': 'WSW',
    'ice storm warning': 'ICW',
    'excessive heat warning': 'EHW',
    'high wind warning': 'HWW',
    'fire warning': 'FRW',
    'volcano warning': 'VOW',
    'emergency action notification': 'EAN',
    'civil danger warning': 'CDW',
    'civil emergency message': 'CEM',
    'child abduction emergency': 'CAE',
    'amber alert': 'CAE',
    'law enforcement warning': 'LEW',
    'blue alert': 'BLU',
    'shelter in place warning': 'SPW',
    'evacuation immediate': 'EVA',
    'nuclear power plant warning': 'NUW',
    'radiological hazard warning': 'RHW',
    'hazardous materials warning': 'HMW',
}

# SAME originator to CAP sender mapping
SAME_ORIGINATOR_TO_SENDER = {
    'WXR': 'w-nws.webmaster@noaa.gov',
    'PEP': 'fema-ipaws@fema.dhs.gov',
    'CIV': 'eas@local.gov',
    'EAS': 'eas@broadcast.local',
}


def cap_to_same(
    cap: CAPAlert,
    callsign: str = 'EAS-WEB',
    default_duration: int = 30
) -> Optional[SAMEMessage]:
    """
    Convert CAP alert to SAME message.

    Args:
        cap: CAPAlert object
        callsign: Station callsign for SAME header
        default_duration: Default duration in minutes if not specified

    Returns:
        SAMEMessage object, or None if conversion not possible
    """
    if not cap.info:
        return None

    info = cap.info[0]

    # determine SAME event code
    same_event = None

    # check eventCode elements for SAME code
    if 'SAME' in info.event_codes:
        same_event = info.event_codes['SAME']
    elif 'same' in info.event_codes:
        same_event = info.event_codes['same']

    # fallback: map from event name
    if not same_event:
        event_lower = info.event.lower()
        for name, code in CAP_TO_SAME_EVENT.items():
            if name in event_lower:
                same_event = code
                break

    if not same_event:
        # can't map this CAP event to SAME
        return None

    # determine originator
    originator = 'EAS'
    if same_event in EVENT_CODES:
        originator = EVENT_CODES[same_event].get('originator', 'EAS')

    # extract FIPS codes from areas
    locations = []
    for area in info.areas:
        # look for FIPS6 or UGC geocodes
        if 'FIPS6' in area.geocodes:
            fips = area.geocodes['FIPS6']
            # FIPS6 format: SSCCC -> need 0SSCCC format
            if len(fips) == 5:
                locations.append(f'0{fips}')
            elif len(fips) == 6:
                locations.append(fips)
        elif 'SAME' in area.geocodes:
            locations.append(area.geocodes['SAME'])

    if not locations:
        # no valid location codes
        return None

    # calculate duration
    duration_minutes = default_duration
    if info.effective and info.expires:
        delta = info.expires - info.effective
        duration_minutes = int(delta.total_seconds() / 60)
        # cap at max SAME duration
        duration_minutes = min(duration_minutes, 9959)

    # get issue time
    issue_time = info.effective or info.onset or cap.sent

    return SAMEMessage.create(
        originator=originator,
        event=same_event,
        locations=locations[:31],  # SAME max 31 locations
        duration_minutes=duration_minutes,
        callsign=callsign[:8],
        issue_datetime=issue_time
    )


def same_to_cap(
    same: SAMEMessage,
    sender: Optional[str] = None,
    headline: Optional[str] = None,
    description: Optional[str] = None,
    instruction: Optional[str] = None,
    area_desc: Optional[str] = None
) -> str:
    """
    Convert SAME message to CAP XML.

    Args:
        same: SAMEMessage object
        sender: CAP sender identifier (defaults based on originator)
        headline: Alert headline
        description: Alert description
        instruction: Response instructions
        area_desc: Area description

    Returns:
        CAP XML string
    """
    # get event info
    event_info = SAME_TO_CAP_EVENT.get(same.event)
    if event_info:
        event_name, category, severity = event_info
    else:
        event_name = EVENT_CODES.get(same.event, {}).get('name', same.event)
        category = CAPCategory.OTHER
        severity = CAPSeverity.UNKNOWN

    # default sender
    if not sender:
        sender = SAME_ORIGINATOR_TO_SENDER.get(same.originator, 'eas@unknown')

    # calculate times
    now = datetime.utcnow()
    issue_year = now.year

    julian_day = int(same.issue_time[:3])
    hour = int(same.issue_time[3:5])
    minute = int(same.issue_time[5:7])

    effective = datetime(issue_year, 1, 1) + timedelta(days=julian_day - 1)
    effective = effective.replace(hour=hour, minute=minute)

    purge_hours = int(same.purge_time[:2])
    purge_minutes = int(same.purge_time[2:4])
    expires = effective + timedelta(hours=purge_hours, minutes=purge_minutes)

    # build identifier
    identifier = f"{same.callsign}-{same.issue_time}-{same.event}"

    # default descriptions
    if not headline:
        headline = f"{event_name} issued by {same.callsign}"
    if not area_desc:
        area_desc = f"FIPS codes: {', '.join(same.locations)}"

    # build XML
    root = ET.Element('alert')
    root.set('xmlns', 'urn:oasis:names:tc:emergency:cap:1.2')

    ET.SubElement(root, 'identifier').text = identifier
    ET.SubElement(root, 'sender').text = sender
    ET.SubElement(root, 'sent').text = effective.strftime('%Y-%m-%dT%H:%M:%S+00:00')

    # status based on event type
    if same.event in ('RWT', 'RMT', 'NPT', 'DMO'):
        ET.SubElement(root, 'status').text = 'Test'
    else:
        ET.SubElement(root, 'status').text = 'Actual'

    ET.SubElement(root, 'msgType').text = 'Alert'
    ET.SubElement(root, 'scope').text = 'Public'

    code = ET.SubElement(root, 'code')
    code.text = 'IPAWSv1.0'

    # info block
    info = ET.SubElement(root, 'info')
    ET.SubElement(info, 'language').text = 'en-US'
    ET.SubElement(info, 'category').text = category.value
    ET.SubElement(info, 'event').text = event_name

    # urgency based on event category
    if same.event in ('TOR', 'TSW', 'EWW', 'EAN', 'CDW', 'EVA', 'NUW'):
        ET.SubElement(info, 'urgency').text = 'Immediate'
    elif same.event in ('SVR', 'FFW', 'HUW', 'CAE', 'LEW'):
        ET.SubElement(info, 'urgency').text = 'Expected'
    else:
        ET.SubElement(info, 'urgency').text = 'Future'

    ET.SubElement(info, 'severity').text = severity.value
    ET.SubElement(info, 'certainty').text = 'Observed'

    # event code
    event_code = ET.SubElement(info, 'eventCode')
    ET.SubElement(event_code, 'valueName').text = 'SAME'
    ET.SubElement(event_code, 'value').text = same.event

    ET.SubElement(info, 'effective').text = effective.strftime('%Y-%m-%dT%H:%M:%S+00:00')
    ET.SubElement(info, 'expires').text = expires.strftime('%Y-%m-%dT%H:%M:%S+00:00')

    ET.SubElement(info, 'senderName').text = same.callsign
    ET.SubElement(info, 'headline').text = headline

    if description:
        ET.SubElement(info, 'description').text = description
    if instruction:
        ET.SubElement(info, 'instruction').text = instruction

    # SAME header parameter
    param = ET.SubElement(info, 'parameter')
    ET.SubElement(param, 'valueName').text = 'SAMEHeader'
    ET.SubElement(param, 'value').text = same.to_string()

    # area with geocodes
    area = ET.SubElement(info, 'area')
    ET.SubElement(area, 'areaDesc').text = area_desc

    for loc in same.locations:
        geocode = ET.SubElement(area, 'geocode')
        ET.SubElement(geocode, 'valueName').text = 'SAME'
        ET.SubElement(geocode, 'value').text = loc

        # also add FIPS6 format
        geocode2 = ET.SubElement(area, 'geocode')
        ET.SubElement(geocode2, 'valueName').text = 'FIPS6'
        # convert 0SSCCC to SSCCC
        ET.SubElement(geocode2, 'value').text = loc[1:] if loc.startswith('0') else loc

    # format XML
    ET.indent(root)
    return ET.tostring(root, encoding='unicode', xml_declaration=True)


def validate_cap_for_same(cap: CAPAlert) -> Dict:
    """
    Validate if a CAP alert can be converted to SAME.

    Returns dict with:
        - convertible: bool
        - issues: list of issues preventing/affecting conversion
        - same_event: detected SAME event code if any
    """
    result = {
        'convertible': False,
        'issues': [],
        'same_event': None
    }

    if not cap.info:
        result['issues'].append('No info block in CAP alert')
        return result

    info = cap.info[0]

    # check for SAME event code
    same_event = None
    if 'SAME' in info.event_codes:
        same_event = info.event_codes['SAME']
    elif 'same' in info.event_codes:
        same_event = info.event_codes['same']
    else:
        event_lower = info.event.lower()
        for name, code in CAP_TO_SAME_EVENT.items():
            if name in event_lower:
                same_event = code
                break

    if not same_event:
        result['issues'].append(f"Cannot map CAP event '{info.event}' to SAME code")
    else:
        result['same_event'] = same_event

    # check for location codes
    has_locations = False
    for area in info.areas:
        if 'FIPS6' in area.geocodes or 'SAME' in area.geocodes:
            has_locations = True
            break

    if not has_locations:
        result['issues'].append('No FIPS6 or SAME geocodes in area definitions')

    # warnings (non-blocking)
    if len(info.areas) > 31:
        result['issues'].append(f'Warning: {len(info.areas)} areas exceed SAME limit of 31')

    if not info.effective:
        result['issues'].append('Warning: No effective time, will use sent time')

    if not info.expires:
        result['issues'].append('Warning: No expires time, will use default duration')

    result['convertible'] = same_event is not None and has_locations
    return result
