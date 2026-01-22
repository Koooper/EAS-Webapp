"""
NWS Alert Feed Client

Fetches real-time alerts from NWS CAP/Atom feeds.
"""

from .feed import NWSFeedClient, NWSAlert, get_alert_summary

__all__ = ['NWSFeedClient', 'NWSAlert', 'get_alert_summary']
