"""
NWS CAP/Atom Feed Client

Fetches alerts from the National Weather Service CAP Atom feed.
Reference: https://alerts.weather.gov/
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
import urllib.request
import urllib.error
import json
import ssl


# NWS API endpoints
NWS_ALERTS_API = 'https://api.weather.gov/alerts/active'
NWS_ALERTS_ATOM = 'https://alerts.weather.gov/cap/us.php?x=0'

# Atom namespace
ATOM_NS = {'atom': 'http://www.w3.org/2005/Atom'}


@dataclass
class NWSAlert:
    """Represents an NWS alert from the feed."""
    id: str
    area_desc: str
    sent: Optional[datetime]
    effective: Optional[datetime]
    onset: Optional[datetime]
    expires: Optional[datetime]
    status: str
    msg_type: str
    category: str
    severity: str
    certainty: str
    urgency: str
    event: str
    sender: str
    sender_name: str
    headline: Optional[str]
    description: Optional[str]
    instruction: Optional[str]
    response: Optional[str]
    parameters: Dict[str, Any] = field(default_factory=dict)
    geocode: Dict[str, List[str]] = field(default_factory=dict)
    cap_url: Optional[str] = None

    @property
    def same_codes(self) -> List[str]:
        """Get SAME location codes from geocode."""
        return self.geocode.get('SAME', [])

    @property
    def ugc_codes(self) -> List[str]:
        """Get UGC codes from geocode."""
        return self.geocode.get('UGC', [])

    @property
    def fips_codes(self) -> List[str]:
        """Get FIPS6 codes from geocode."""
        return self.geocode.get('FIPS6', [])

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'area_desc': self.area_desc,
            'sent': self.sent.isoformat() if self.sent else None,
            'effective': self.effective.isoformat() if self.effective else None,
            'onset': self.onset.isoformat() if self.onset else None,
            'expires': self.expires.isoformat() if self.expires else None,
            'status': self.status,
            'msg_type': self.msg_type,
            'category': self.category,
            'severity': self.severity,
            'certainty': self.certainty,
            'urgency': self.urgency,
            'event': self.event,
            'sender': self.sender,
            'sender_name': self.sender_name,
            'headline': self.headline,
            'description': self.description,
            'instruction': self.instruction,
            'response': self.response,
            'same_codes': self.same_codes,
            'ugc_codes': self.ugc_codes,
            'fips_codes': self.fips_codes,
            'cap_url': self.cap_url
        }


def _parse_datetime(text: Optional[str]) -> Optional[datetime]:
    """Parse ISO 8601 datetime string."""
    if not text:
        return None
    try:
        # handle timezone suffix
        return datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        return None


class NWSFeedClient:
    """
    Client for fetching NWS alerts.

    Supports both the JSON API and Atom/CAP feed.
    """

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self._ssl_context = ssl.create_default_context()

    def _fetch_url(self, url: str, headers: Optional[Dict[str, str]] = None) -> bytes:
        """Fetch URL with proper headers."""
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'EAS-Webapp/1.0 (github.com/eas-webapp)')
        req.add_header('Accept', 'application/geo+json, application/json, application/atom+xml')

        if headers:
            for key, value in headers.items():
                req.add_header(key, value)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=self._ssl_context) as response:
                return response.read()
        except urllib.error.URLError as e:
            raise ConnectionError(f"Failed to fetch {url}: {e}")

    def get_active_alerts(
        self,
        area: Optional[str] = None,
        event: Optional[str] = None,
        urgency: Optional[str] = None,
        severity: Optional[str] = None,
        certainty: Optional[str] = None,
        status: str = 'actual',
        limit: int = 50
    ) -> List[NWSAlert]:
        """
        Fetch active alerts from NWS API.

        Args:
            area: State/territory code (e.g., 'TX', 'CA')
            event: Event type filter (e.g., 'Tornado Warning')
            urgency: Urgency filter (Immediate, Expected, Future, Past, Unknown)
            severity: Severity filter (Extreme, Severe, Moderate, Minor, Unknown)
            certainty: Certainty filter (Observed, Likely, Possible, Unlikely, Unknown)
            status: Status filter (actual, exercise, system, test, draft)
            limit: Maximum number of alerts to return

        Returns:
            List of NWSAlert objects
        """
        params = [f'status={status}', f'limit={limit}']

        if area:
            params.append(f'area={area}')
        if event:
            params.append(f'event={urllib.parse.quote(event)}')
        if urgency:
            params.append(f'urgency={urgency}')
        if severity:
            params.append(f'severity={severity}')
        if certainty:
            params.append(f'certainty={certainty}')

        url = f"{NWS_ALERTS_API}?{'&'.join(params)}"

        try:
            data = self._fetch_url(url)
            return self._parse_json_response(json.loads(data))
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON response: {e}")

    def get_alerts_by_state(self, state_code: str, limit: int = 50) -> List[NWSAlert]:
        """Get active alerts for a specific state."""
        return self.get_active_alerts(area=state_code.upper(), limit=limit)

    def get_alerts_by_event(self, event_type: str, limit: int = 50) -> List[NWSAlert]:
        """Get active alerts of a specific type."""
        return self.get_active_alerts(event=event_type, limit=limit)

    def get_severe_alerts(self, limit: int = 50) -> List[NWSAlert]:
        """Get alerts with Extreme or Severe severity."""
        extreme = self.get_active_alerts(severity='Extreme', limit=limit)
        severe = self.get_active_alerts(severity='Severe', limit=limit)
        # deduplicate by id
        seen = set()
        result = []
        for alert in extreme + severe:
            if alert.id not in seen:
                seen.add(alert.id)
                result.append(alert)
        return result[:limit]

    def _parse_json_response(self, data: Dict[str, Any]) -> List[NWSAlert]:
        """Parse NWS API JSON response."""
        alerts = []

        for feature in data.get('features', []):
            props = feature.get('properties', {})

            geocode = {}
            for key, values in props.get('geocode', {}).items():
                geocode[key] = values if isinstance(values, list) else [values]

            alert = NWSAlert(
                id=props.get('id', ''),
                area_desc=props.get('areaDesc', ''),
                sent=_parse_datetime(props.get('sent')),
                effective=_parse_datetime(props.get('effective')),
                onset=_parse_datetime(props.get('onset')),
                expires=_parse_datetime(props.get('expires')),
                status=props.get('status', ''),
                msg_type=props.get('messageType', ''),
                category=props.get('category', ''),
                severity=props.get('severity', ''),
                certainty=props.get('certainty', ''),
                urgency=props.get('urgency', ''),
                event=props.get('event', ''),
                sender=props.get('sender', ''),
                sender_name=props.get('senderName', ''),
                headline=props.get('headline'),
                description=props.get('description'),
                instruction=props.get('instruction'),
                response=props.get('response'),
                parameters=props.get('parameters', {}),
                geocode=geocode,
                cap_url=props.get('@id')
            )
            alerts.append(alert)

        return alerts

    def get_alert_cap(self, alert_id: str) -> Optional[str]:
        """
        Fetch the raw CAP XML for a specific alert.

        Args:
            alert_id: The alert ID or URL

        Returns:
            CAP XML string or None if not found
        """
        # construct URL if just an ID
        if not alert_id.startswith('http'):
            url = f"https://api.weather.gov/alerts/{alert_id}"
        else:
            url = alert_id

        try:
            data = self._fetch_url(url, headers={'Accept': 'application/cap+xml'})
            return data.decode('utf-8')
        except Exception:
            return None


def get_alert_summary() -> Dict[str, Any]:
    """
    Get a summary of current active alerts.

    Returns dict with counts by severity, event type, and state.
    """
    client = NWSFeedClient()
    alerts = client.get_active_alerts(limit=500)

    summary = {
        'total': len(alerts),
        'by_severity': {},
        'by_event': {},
        'by_state': {},
        'by_urgency': {}
    }

    for alert in alerts:
        # count by severity
        sev = alert.severity or 'Unknown'
        summary['by_severity'][sev] = summary['by_severity'].get(sev, 0) + 1

        # count by event
        evt = alert.event or 'Unknown'
        summary['by_event'][evt] = summary['by_event'].get(evt, 0) + 1

        # count by urgency
        urg = alert.urgency or 'Unknown'
        summary['by_urgency'][urg] = summary['by_urgency'].get(urg, 0) + 1

        # count by state (from UGC codes)
        for ugc in alert.ugc_codes:
            state = ugc[:2]
            summary['by_state'][state] = summary['by_state'].get(state, 0) + 1

    return summary
