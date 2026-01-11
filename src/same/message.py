"""
SAME message structure and validation per 47 CFR 11.31

Message format: ZCZC-ORG-EEE-PSSCCC[-PSSCCC...]+TTTT-JJJHHMM-LLLLLLLL-

Where:
- ORG: Originator code (3 chars)
- EEE: Event code (3 chars)
- PSSCCC: Location code(s) - P=part, SS=state, CCC=county FIPS
- TTTT: Purge time in HHMM format
- JJJHHMM: Issue time - Julian day + UTC time
- LLLLLLLL: Callsign (up to 8 chars)
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime, timedelta


@dataclass
class SAMEMessage:
    """
    Represents a parsed or constructed SAME message.
    """
    originator: str
    event: str
    locations: List[str]
    purge_time: str  # HHMM format
    issue_time: str  # JJJHHMM format
    callsign: str

    # regex for validation
    HEADER_PATTERN = re.compile(
        r'^ZCZC-'
        r'([A-Z]{3})-'           # originator
        r'([A-Z]{3})-'           # event code
        r'(\d{6}(?:-\d{6})*)'    # location codes
        r'\+(\d{4})-'            # purge time
        r'(\d{7})-'              # issue time
        r'([A-Z0-9/\-]{1,8})-$'  # callsign
    )

    def __post_init__(self):
        """Validate fields after initialization."""
        if len(self.originator) != 3:
            raise ValueError(f"Originator must be 3 characters: {self.originator}")
        if len(self.event) != 3:
            raise ValueError(f"Event code must be 3 characters: {self.event}")
        if not self.locations:
            raise ValueError("At least one location code required")
        for loc in self.locations:
            if not re.match(r'^\d{6}$', loc):
                raise ValueError(f"Invalid location code: {loc}")
        if not re.match(r'^\d{4}$', self.purge_time):
            raise ValueError(f"Purge time must be HHMM: {self.purge_time}")
        if not re.match(r'^\d{7}$', self.issue_time):
            raise ValueError(f"Issue time must be JJJHHMM: {self.issue_time}")
        if len(self.callsign) > 8:
            raise ValueError(f"Callsign max 8 characters: {self.callsign}")

    @classmethod
    def parse(cls, header: str) -> 'SAMEMessage':
        """
        Parse a SAME header string into a SAMEMessage object.

        Args:
            header: Full SAME header string (with or without ZCZC- prefix)

        Returns:
            SAMEMessage instance
        """
        # normalize header
        header = header.strip().upper()
        if not header.startswith('ZCZC-'):
            header = f'ZCZC-{header}'
        if not header.endswith('-'):
            header = f'{header}-'

        match = cls.HEADER_PATTERN.match(header)
        if not match:
            raise ValueError(f"Invalid SAME header format: {header}")

        originator = match.group(1)
        event = match.group(2)
        locations = match.group(3).split('-')
        purge_time = match.group(4)
        issue_time = match.group(5)
        callsign = match.group(6)

        return cls(
            originator=originator,
            event=event,
            locations=locations,
            purge_time=purge_time,
            issue_time=issue_time,
            callsign=callsign
        )

    def to_string(self) -> str:
        """Generate the SAME header string."""
        locations_str = '-'.join(self.locations)
        return f"ZCZC-{self.originator}-{self.event}-{locations_str}+{self.purge_time}-{self.issue_time}-{self.callsign}-"

    @classmethod
    def create(
        cls,
        originator: str,
        event: str,
        locations: List[str],
        duration_minutes: int,
        callsign: str,
        issue_datetime: Optional[datetime] = None
    ) -> 'SAMEMessage':
        """
        Create a new SAME message with automatic time calculation.

        Args:
            originator: 3-letter originator code (WXR, PEP, CIV, EAS)
            event: 3-letter event code (TOR, SVR, EAN, etc.)
            locations: List of 6-digit location codes
            duration_minutes: Alert duration in minutes (max 9959)
            callsign: Station callsign (max 8 chars)
            issue_datetime: Issue time (defaults to now)

        Returns:
            SAMEMessage instance
        """
        if issue_datetime is None:
            issue_datetime = datetime.utcnow()

        # calculate julian day and time
        julian_day = issue_datetime.timetuple().tm_yday
        issue_time = f"{julian_day:03d}{issue_datetime.hour:02d}{issue_datetime.minute:02d}"

        # format purge time
        hours = duration_minutes // 60
        minutes = duration_minutes % 60
        purge_time = f"{hours:02d}{minutes:02d}"

        return cls(
            originator=originator.upper(),
            event=event.upper(),
            locations=locations,
            purge_time=purge_time,
            issue_time=issue_time,
            callsign=callsign.upper()
        )

    def get_expiry_datetime(self, issue_year: Optional[int] = None) -> datetime:
        """
        Calculate when this alert expires.

        Args:
            issue_year: Year to use for calculation (defaults to current year)

        Returns:
            Expiration datetime
        """
        if issue_year is None:
            issue_year = datetime.utcnow().year

        julian_day = int(self.issue_time[:3])
        hour = int(self.issue_time[3:5])
        minute = int(self.issue_time[5:7])

        issue_dt = datetime(issue_year, 1, 1) + timedelta(days=julian_day - 1)
        issue_dt = issue_dt.replace(hour=hour, minute=minute)

        purge_hours = int(self.purge_time[:2])
        purge_minutes = int(self.purge_time[2:4])

        return issue_dt + timedelta(hours=purge_hours, minutes=purge_minutes)

    def __str__(self) -> str:
        return self.to_string()

    def __repr__(self) -> str:
        return f"SAMEMessage({self.to_string()})"
