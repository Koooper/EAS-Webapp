"""
CAP v1.2 XML Parser

Parses Common Alerting Protocol XML per OASIS CAP v1.2 specification.
Reference: http://docs.oasis-open.org/emergency/cap/v1.2/CAP-v1.2.html
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum


# CAP namespaces
CAP_NS = {
    'cap': 'urn:oasis:names:tc:emergency:cap:1.2',
    'cap11': 'urn:oasis:names:tc:emergency:cap:1.1',
}


class CAPStatus(Enum):
    ACTUAL = 'Actual'
    EXERCISE = 'Exercise'
    SYSTEM = 'System'
    TEST = 'Test'
    DRAFT = 'Draft'


class CAPMsgType(Enum):
    ALERT = 'Alert'
    UPDATE = 'Update'
    CANCEL = 'Cancel'
    ACK = 'Ack'
    ERROR = 'Error'


class CAPScope(Enum):
    PUBLIC = 'Public'
    RESTRICTED = 'Restricted'
    PRIVATE = 'Private'


class CAPCategory(Enum):
    GEO = 'Geo'
    MET = 'Met'
    SAFETY = 'Safety'
    SECURITY = 'Security'
    RESCUE = 'Rescue'
    FIRE = 'Fire'
    HEALTH = 'Health'
    ENV = 'Env'
    TRANSPORT = 'Transport'
    INFRA = 'Infra'
    CBRNE = 'CBRNE'
    OTHER = 'Other'


class CAPUrgency(Enum):
    IMMEDIATE = 'Immediate'
    EXPECTED = 'Expected'
    FUTURE = 'Future'
    PAST = 'Past'
    UNKNOWN = 'Unknown'


class CAPSeverity(Enum):
    EXTREME = 'Extreme'
    SEVERE = 'Severe'
    MODERATE = 'Moderate'
    MINOR = 'Minor'
    UNKNOWN = 'Unknown'


class CAPCertainty(Enum):
    OBSERVED = 'Observed'
    LIKELY = 'Likely'
    POSSIBLE = 'Possible'
    UNLIKELY = 'Unlikely'
    UNKNOWN = 'Unknown'


class CAPResponseType(Enum):
    SHELTER = 'Shelter'
    EVACUATE = 'Evacuate'
    PREPARE = 'Prepare'
    EXECUTE = 'Execute'
    AVOID = 'Avoid'
    MONITOR = 'Monitor'
    ASSESS = 'Assess'
    ALL_CLEAR = 'AllClear'
    NONE = 'None'


@dataclass
class CAPArea:
    """Geographic area affected by alert."""
    area_desc: str
    polygons: List[str] = field(default_factory=list)
    circles: List[str] = field(default_factory=list)
    geocodes: Dict[str, str] = field(default_factory=dict)
    altitude: Optional[float] = None
    ceiling: Optional[float] = None


@dataclass
class CAPInfo:
    """Alert information block (language-specific)."""
    language: str = 'en-US'
    categories: List[CAPCategory] = field(default_factory=list)
    event: str = ''
    response_types: List[CAPResponseType] = field(default_factory=list)
    urgency: CAPUrgency = CAPUrgency.UNKNOWN
    severity: CAPSeverity = CAPSeverity.UNKNOWN
    certainty: CAPCertainty = CAPCertainty.UNKNOWN
    audience: Optional[str] = None
    event_codes: Dict[str, str] = field(default_factory=dict)
    effective: Optional[datetime] = None
    onset: Optional[datetime] = None
    expires: Optional[datetime] = None
    sender_name: Optional[str] = None
    headline: Optional[str] = None
    description: Optional[str] = None
    instruction: Optional[str] = None
    web: Optional[str] = None
    contact: Optional[str] = None
    parameters: Dict[str, str] = field(default_factory=dict)
    areas: List[CAPArea] = field(default_factory=list)


@dataclass
class CAPAlert:
    """
    Represents a parsed CAP alert message.

    A CAP alert contains:
    - Header elements (identifier, sender, status, etc.)
    - One or more info blocks (language-specific content)
    - Each info block may have multiple area definitions
    """
    identifier: str
    sender: str
    sent: datetime
    status: CAPStatus
    msg_type: CAPMsgType
    scope: CAPScope
    source: Optional[str] = None
    restriction: Optional[str] = None
    addresses: Optional[str] = None
    codes: List[str] = field(default_factory=list)
    note: Optional[str] = None
    references: Optional[str] = None
    incidents: Optional[str] = None
    info: List[CAPInfo] = field(default_factory=list)

    @property
    def is_actual(self) -> bool:
        return self.status == CAPStatus.ACTUAL

    @property
    def primary_info(self) -> Optional[CAPInfo]:
        """Get primary (first) info block."""
        return self.info[0] if self.info else None


def _parse_datetime(text: Optional[str]) -> Optional[datetime]:
    """Parse CAP datetime string (ISO 8601)."""
    if not text:
        return None
    # CAP uses ISO 8601 with timezone
    # formats: 2024-01-15T12:00:00-05:00 or 2024-01-15T17:00:00+00:00
    text = text.strip()
    try:
        # python 3.11+ supports this directly
        return datetime.fromisoformat(text)
    except ValueError:
        # fallback for older python - strip timezone
        if '+' in text:
            text = text[:text.rfind('+')]
        elif text.count('-') > 2:
            text = text[:text.rfind('-')]
        return datetime.fromisoformat(text)


def _get_text(elem: Optional[ET.Element]) -> Optional[str]:
    """Get element text, or None if element doesn't exist."""
    return elem.text.strip() if elem is not None and elem.text else None


def _find_ns(parent: ET.Element, tag: str) -> Optional[ET.Element]:
    """Find element with namespace fallback."""
    # try CAP 1.2 namespace
    elem = parent.find(f'cap:{tag}', CAP_NS)
    if elem is None:
        # try CAP 1.1 namespace
        elem = parent.find(f'cap11:{tag}', CAP_NS)
    if elem is None:
        # try no namespace
        elem = parent.find(tag)
    return elem


def _findall_ns(parent: ET.Element, tag: str) -> List[ET.Element]:
    """Find all elements with namespace fallback."""
    elems = parent.findall(f'cap:{tag}', CAP_NS)
    if not elems:
        elems = parent.findall(f'cap11:{tag}', CAP_NS)
    if not elems:
        elems = parent.findall(tag)
    return elems


def _parse_area(area_elem: ET.Element) -> CAPArea:
    """Parse CAP area element."""
    area = CAPArea(
        area_desc=_get_text(_find_ns(area_elem, 'areaDesc')) or 'Unknown Area'
    )

    for polygon in _findall_ns(area_elem, 'polygon'):
        if polygon.text:
            area.polygons.append(polygon.text.strip())

    for circle in _findall_ns(area_elem, 'circle'):
        if circle.text:
            area.circles.append(circle.text.strip())

    for geocode in _findall_ns(area_elem, 'geocode'):
        name = _get_text(_find_ns(geocode, 'valueName'))
        value = _get_text(_find_ns(geocode, 'value'))
        if name and value:
            area.geocodes[name] = value

    altitude = _get_text(_find_ns(area_elem, 'altitude'))
    if altitude:
        area.altitude = float(altitude)

    ceiling = _get_text(_find_ns(area_elem, 'ceiling'))
    if ceiling:
        area.ceiling = float(ceiling)

    return area


def _parse_info(info_elem: ET.Element) -> CAPInfo:
    """Parse CAP info element."""
    info = CAPInfo()

    info.language = _get_text(_find_ns(info_elem, 'language')) or 'en-US'

    for cat in _findall_ns(info_elem, 'category'):
        if cat.text:
            try:
                info.categories.append(CAPCategory(cat.text.strip()))
            except ValueError:
                pass

    info.event = _get_text(_find_ns(info_elem, 'event')) or ''

    for rt in _findall_ns(info_elem, 'responseType'):
        if rt.text:
            try:
                info.response_types.append(CAPResponseType(rt.text.strip()))
            except ValueError:
                pass

    urgency = _get_text(_find_ns(info_elem, 'urgency'))
    if urgency:
        try:
            info.urgency = CAPUrgency(urgency)
        except ValueError:
            pass

    severity = _get_text(_find_ns(info_elem, 'severity'))
    if severity:
        try:
            info.severity = CAPSeverity(severity)
        except ValueError:
            pass

    certainty = _get_text(_find_ns(info_elem, 'certainty'))
    if certainty:
        try:
            info.certainty = CAPCertainty(certainty)
        except ValueError:
            pass

    info.audience = _get_text(_find_ns(info_elem, 'audience'))

    for ec in _findall_ns(info_elem, 'eventCode'):
        name = _get_text(_find_ns(ec, 'valueName'))
        value = _get_text(_find_ns(ec, 'value'))
        if name and value:
            info.event_codes[name] = value

    info.effective = _parse_datetime(_get_text(_find_ns(info_elem, 'effective')))
    info.onset = _parse_datetime(_get_text(_find_ns(info_elem, 'onset')))
    info.expires = _parse_datetime(_get_text(_find_ns(info_elem, 'expires')))

    info.sender_name = _get_text(_find_ns(info_elem, 'senderName'))
    info.headline = _get_text(_find_ns(info_elem, 'headline'))
    info.description = _get_text(_find_ns(info_elem, 'description'))
    info.instruction = _get_text(_find_ns(info_elem, 'instruction'))
    info.web = _get_text(_find_ns(info_elem, 'web'))
    info.contact = _get_text(_find_ns(info_elem, 'contact'))

    for param in _findall_ns(info_elem, 'parameter'):
        name = _get_text(_find_ns(param, 'valueName'))
        value = _get_text(_find_ns(param, 'value'))
        if name and value:
            info.parameters[name] = value

    for area_elem in _findall_ns(info_elem, 'area'):
        info.areas.append(_parse_area(area_elem))

    return info


def parse_cap(xml_string: str) -> CAPAlert:
    """
    Parse CAP XML string into CAPAlert object.

    Args:
        xml_string: CAP XML content

    Returns:
        CAPAlert object

    Raises:
        ValueError: If XML is invalid or missing required elements
    """
    try:
        root = ET.fromstring(xml_string)
    except ET.ParseError as e:
        raise ValueError(f"Invalid XML: {e}")

    # handle namespaced root
    tag = root.tag
    if '}' in tag:
        tag = tag.split('}')[1]

    if tag != 'alert':
        raise ValueError(f"Root element must be 'alert', got '{tag}'")

    # required elements
    identifier = _get_text(_find_ns(root, 'identifier'))
    if not identifier:
        raise ValueError("Missing required element: identifier")

    sender = _get_text(_find_ns(root, 'sender'))
    if not sender:
        raise ValueError("Missing required element: sender")

    sent_text = _get_text(_find_ns(root, 'sent'))
    if not sent_text:
        raise ValueError("Missing required element: sent")
    sent = _parse_datetime(sent_text)
    if not sent:
        raise ValueError(f"Invalid sent datetime: {sent_text}")

    status_text = _get_text(_find_ns(root, 'status'))
    if not status_text:
        raise ValueError("Missing required element: status")
    try:
        status = CAPStatus(status_text)
    except ValueError:
        raise ValueError(f"Invalid status: {status_text}")

    msg_type_text = _get_text(_find_ns(root, 'msgType'))
    if not msg_type_text:
        raise ValueError("Missing required element: msgType")
    try:
        msg_type = CAPMsgType(msg_type_text)
    except ValueError:
        raise ValueError(f"Invalid msgType: {msg_type_text}")

    scope_text = _get_text(_find_ns(root, 'scope'))
    if not scope_text:
        raise ValueError("Missing required element: scope")
    try:
        scope = CAPScope(scope_text)
    except ValueError:
        raise ValueError(f"Invalid scope: {scope_text}")

    alert = CAPAlert(
        identifier=identifier,
        sender=sender,
        sent=sent,
        status=status,
        msg_type=msg_type,
        scope=scope,
        source=_get_text(_find_ns(root, 'source')),
        restriction=_get_text(_find_ns(root, 'restriction')),
        addresses=_get_text(_find_ns(root, 'addresses')),
        note=_get_text(_find_ns(root, 'note')),
        references=_get_text(_find_ns(root, 'references')),
        incidents=_get_text(_find_ns(root, 'incidents'))
    )

    for code in _findall_ns(root, 'code'):
        if code.text:
            alert.codes.append(code.text.strip())

    for info_elem in _findall_ns(root, 'info'):
        alert.info.append(_parse_info(info_elem))

    return alert


def parse_cap_file(filepath: str) -> CAPAlert:
    """
    Parse CAP XML file.

    Args:
        filepath: Path to CAP XML file

    Returns:
        CAPAlert object
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        return parse_cap(f.read())
