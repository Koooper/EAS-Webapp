"""
CAP (Common Alerting Protocol) parser and converter

Implements OASIS CAP v1.2 standard for alert interchange.
Provides bidirectional conversion between CAP XML and SAME headers.
"""

from .parser import CAPAlert, CAPInfo, CAPArea, parse_cap, parse_cap_file
from .converter import cap_to_same, same_to_cap, validate_cap_for_same

__all__ = [
    'CAPAlert', 'CAPInfo', 'CAPArea',
    'parse_cap', 'parse_cap_file',
    'cap_to_same', 'same_to_cap', 'validate_cap_for_same'
]
