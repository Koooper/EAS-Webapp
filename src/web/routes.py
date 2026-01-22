"""
Flask routes for EAS Webapp
"""

from flask import Blueprint, request, jsonify, send_file, render_template_string
import io
import base64
from datetime import datetime

from ..same import SAMEEncoder, SAMEDecoder, SAMEMessage
from ..eas import (
    EVENT_CODES, ORIGINATOR_CODES,
    get_event_description, get_originator_description,
    get_state_name, format_location_code
)
from ..eas.fips import STATE_CODES, _load_county_data

# TTS import with fallback
try:
    from ..tts import TTSSynthesizer, VoiceStyle
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

# CAP import with fallback
try:
    from ..cap import parse_cap, cap_to_same, same_to_cap, validate_cap_for_same, CAPAlert
    CAP_AVAILABLE = True
except ImportError:
    CAP_AVAILABLE = False

# NWS feed import with fallback
try:
    from ..nws import NWSFeedClient, NWSAlert
    from ..nws.feed import get_alert_summary
    NWS_AVAILABLE = True
except ImportError:
    NWS_AVAILABLE = False

# Batch processing import with fallback
try:
    from ..batch import BatchProcessor, parse_csv_batch, parse_json_batch
    BATCH_AVAILABLE = True
    _batch_processor = BatchProcessor()
except ImportError:
    BATCH_AVAILABLE = False
    _batch_processor = None

# Alert archive import with fallback
try:
    from ..archive import AlertArchive
    ARCHIVE_AVAILABLE = True
    _alert_archive = AlertArchive()
except ImportError:
    ARCHIVE_AVAILABLE = False
    _alert_archive = None

api_bp = Blueprint('api', __name__)
views_bp = Blueprint('views', __name__)


@api_bp.route('/encode', methods=['POST'])
def encode_message():
    """
    Encode a SAME message to audio.

    Request JSON:
        originator: str - originator code (WXR, PEP, CIV, EAS)
        event: str - event code (TOR, SVR, etc.)
        locations: list[str] - FIPS location codes
        duration: int - alert duration in minutes
        callsign: str - station callsign
        attention_duration: float - attention tone duration (optional, default 8)

    Returns:
        JSON with header string and base64 audio
    """
    data = request.get_json()

    try:
        # create message
        msg = SAMEMessage.create(
            originator=data['originator'],
            event=data['event'],
            locations=data['locations'],
            duration_minutes=data['duration'],
            callsign=data['callsign']
        )

        # encode to audio
        encoder = SAMEEncoder()
        attention_duration = data.get('attention_duration', 8)

        audio = encoder.encode_full_alert(
            header=msg.to_string(),
            attention_duration=attention_duration
        )

        # convert to base64 for JSON response
        wav_bytes = encoder.to_bytes(audio)
        audio_b64 = base64.b64encode(wav_bytes).decode('utf-8')

        return jsonify({
            'success': True,
            'header': msg.to_string(),
            'audio': audio_b64,
            'audio_format': 'wav',
            'parsed': {
                'originator': msg.originator,
                'originator_name': get_originator_description(msg.originator),
                'event': msg.event,
                'event_name': get_event_description(msg.event),
                'locations': msg.locations,
                'locations_formatted': [format_location_code(loc) for loc in msg.locations],
                'purge_time': msg.purge_time,
                'issue_time': msg.issue_time,
                'callsign': msg.callsign
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@api_bp.route('/encode/header-only', methods=['POST'])
def encode_header_only():
    """
    Encode just the SAME header (no attention tone or EOM).
    Useful for testing or partial generation.
    """
    data = request.get_json()

    try:
        msg = SAMEMessage.create(
            originator=data['originator'],
            event=data['event'],
            locations=data['locations'],
            duration_minutes=data['duration'],
            callsign=data['callsign']
        )

        encoder = SAMEEncoder()
        audio = encoder.encode_header(msg.to_string())
        wav_bytes = encoder.to_bytes(audio)
        audio_b64 = base64.b64encode(wav_bytes).decode('utf-8')

        return jsonify({
            'success': True,
            'header': msg.to_string(),
            'audio': audio_b64
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@api_bp.route('/decode', methods=['POST'])
def decode_message():
    """
    Decode a SAME message from audio.

    Accepts:
        - File upload (multipart/form-data with 'audio' field)
        - JSON with base64 audio

    Returns:
        JSON with decoded messages
    """
    decoder = SAMEDecoder()

    try:
        if request.content_type and 'multipart/form-data' in request.content_type:
            # file upload
            if 'audio' not in request.files:
                return jsonify({'success': False, 'error': 'No audio file provided'}), 400

            file = request.files['audio']
            audio_bytes = file.read()
        else:
            # JSON with base64
            data = request.get_json()
            audio_bytes = base64.b64decode(data['audio'])

        messages = decoder.decode_bytes(audio_bytes)

        # parse any headers found
        parsed = []
        for msg in messages:
            if msg.startswith('ZCZC'):
                try:
                    same_msg = SAMEMessage.parse(msg)
                    parsed.append({
                        'raw': msg,
                        'type': 'header',
                        'originator': same_msg.originator,
                        'originator_name': get_originator_description(same_msg.originator),
                        'event': same_msg.event,
                        'event_name': get_event_description(same_msg.event),
                        'locations': same_msg.locations,
                        'locations_formatted': [format_location_code(loc) for loc in same_msg.locations],
                        'purge_time': same_msg.purge_time,
                        'issue_time': same_msg.issue_time,
                        'callsign': same_msg.callsign
                    })
                except ValueError as e:
                    parsed.append({
                        'raw': msg,
                        'type': 'header',
                        'parse_error': str(e)
                    })
            elif msg == 'NNNN':
                parsed.append({
                    'raw': msg,
                    'type': 'eom'
                })

        return jsonify({
            'success': True,
            'messages': parsed,
            'raw_messages': messages
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@api_bp.route('/parse', methods=['POST'])
def parse_header():
    """
    Parse a SAME header string (text, not audio).

    Request JSON:
        header: str - SAME header string

    Returns:
        Parsed message components
    """
    data = request.get_json()

    try:
        msg = SAMEMessage.parse(data['header'])

        return jsonify({
            'success': True,
            'raw': msg.to_string(),
            'originator': msg.originator,
            'originator_name': get_originator_description(msg.originator),
            'event': msg.event,
            'event_name': get_event_description(msg.event),
            'locations': msg.locations,
            'locations_formatted': [format_location_code(loc) for loc in msg.locations],
            'purge_time': msg.purge_time,
            'issue_time': msg.issue_time,
            'callsign': msg.callsign
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@api_bp.route('/codes/events', methods=['GET'])
def get_event_codes():
    """Get all event codes with descriptions."""
    return jsonify(EVENT_CODES)


@api_bp.route('/codes/originators', methods=['GET'])
def get_originator_codes():
    """Get all originator codes."""
    return jsonify(ORIGINATOR_CODES)


@api_bp.route('/codes/states', methods=['GET'])
def get_states():
    """Get all state FIPS codes."""
    return jsonify(STATE_CODES)


@api_bp.route('/codes/counties/<state_code>', methods=['GET'])
def get_counties(state_code):
    """
    Get all counties for a state.

    Args:
        state_code: 2-digit state FIPS code

    Returns:
        JSON dict of county code -> county name
    """
    counties = _load_county_data()
    state_code = state_code.zfill(2)

    if state_code in counties:
        return jsonify(counties[state_code])
    else:
        return jsonify({'error': f'State code {state_code} not found'}), 404


@api_bp.route('/attention-tone', methods=['GET'])
def get_attention_tone():
    """
    Get just the attention tone audio.
    Query params:
        duration: float - duration in seconds (default 8)
    """
    duration = float(request.args.get('duration', 8))

    encoder = SAMEEncoder()
    audio = encoder.generate_attention_signal(duration)
    wav_bytes = encoder.to_bytes(audio)

    return send_file(
        io.BytesIO(wav_bytes),
        mimetype='audio/wav',
        as_attachment=False,
        download_name='attention.wav'
    )


@api_bp.route('/tts/status', methods=['GET'])
def tts_status():
    """Check TTS availability and backend."""
    if not TTS_AVAILABLE:
        return jsonify({
            'available': False,
            'backend': None,
            'voices': []
        })

    try:
        synth = TTSSynthesizer()
        return jsonify({
            'available': synth.available,
            'backend': synth.backend_name,
            'voices': [
                {'id': v.value, 'name': v.name}
                for v in VoiceStyle
            ]
        })
    except Exception as e:
        return jsonify({
            'available': False,
            'backend': None,
            'error': str(e)
        })


@api_bp.route('/tts/synthesize', methods=['POST'])
def synthesize_voice():
    """
    Synthesize voice message.

    Request JSON:
        text: str - text to synthesize
        voice: str - voice style (optional)

    Returns:
        JSON with base64 audio
    """
    if not TTS_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'TTS not available. Install edge-tts or pyttsx3.'
        }), 400

    data = request.get_json()

    try:
        voice_name = data.get('voice', 'DEFAULT')
        try:
            voice = VoiceStyle[voice_name]
        except KeyError:
            voice = VoiceStyle.DEFAULT

        synth = TTSSynthesizer(voice=voice)

        if not synth.available:
            return jsonify({
                'success': False,
                'error': 'No TTS backend available'
            }), 400

        audio = synth.synthesize(data['text'])

        encoder = SAMEEncoder()
        wav_bytes = encoder.to_bytes(audio)
        audio_b64 = base64.b64encode(wav_bytes).decode('utf-8')

        return jsonify({
            'success': True,
            'audio': audio_b64,
            'backend': synth.backend_name
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@api_bp.route('/encode/with-voice', methods=['POST'])
def encode_with_voice():
    """
    Encode a complete EAS alert with TTS voice message.

    Request JSON:
        originator: str
        event: str
        locations: list[str]
        duration: int
        callsign: str
        attention_duration: float (optional)
        voice_text: str (optional) - custom voice message
        voice: str (optional) - voice style

    Returns:
        JSON with header string and base64 audio
    """
    data = request.get_json()

    try:
        msg = SAMEMessage.create(
            originator=data['originator'],
            event=data['event'],
            locations=data['locations'],
            duration_minutes=data['duration'],
            callsign=data['callsign']
        )

        encoder = SAMEEncoder()
        attention_duration = data.get('attention_duration', 8)

        # generate voice audio if TTS available
        voice_audio = None
        if TTS_AVAILABLE and data.get('include_voice', True):
            try:
                voice_name = data.get('voice', 'DEFAULT')
                try:
                    voice = VoiceStyle[voice_name]
                except KeyError:
                    voice = VoiceStyle.DEFAULT

                synth = TTSSynthesizer(voice=voice)

                if synth.available:
                    # use custom text or generate standard announcement
                    if 'voice_text' in data:
                        voice_audio = synth.synthesize(data['voice_text'])
                    else:
                        event_name = get_event_description(msg.event)
                        originator_name = get_originator_description(msg.originator)
                        location_names = [format_location_code(loc) for loc in msg.locations]

                        voice_audio = synth.generate_eas_announcement(
                            event_name=event_name,
                            locations=location_names,
                            originator=originator_name,
                            callsign=msg.callsign
                        )
            except Exception as e:
                # TTS failed, continue without voice
                print(f"TTS failed: {e}")

        audio = encoder.encode_full_alert(
            header=msg.to_string(),
            attention_duration=attention_duration,
            voice_audio=voice_audio
        )

        wav_bytes = encoder.to_bytes(audio)
        audio_b64 = base64.b64encode(wav_bytes).decode('utf-8')

        return jsonify({
            'success': True,
            'header': msg.to_string(),
            'audio': audio_b64,
            'audio_format': 'wav',
            'has_voice': voice_audio is not None,
            'parsed': {
                'originator': msg.originator,
                'originator_name': get_originator_description(msg.originator),
                'event': msg.event,
                'event_name': get_event_description(msg.event),
                'locations': msg.locations,
                'locations_formatted': [format_location_code(loc) for loc in msg.locations],
                'purge_time': msg.purge_time,
                'issue_time': msg.issue_time,
                'callsign': msg.callsign
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


# Simple HTML frontend for views_bp
INDEX_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes">
    <meta name="description" content="Emergency Alert System encoder/decoder with SAME protocol support">
    <meta name="theme-color" content="#ff3333">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="EAS Webapp">
    <title>EAS Webapp</title>
    <link rel="manifest" href="/static/manifest.json">
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
    <div id="app"></div>
    <script src="/static/js/app.js"></script>
    <script>
        // Register service worker for PWA
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/static/sw.js')
                .then(reg => console.log('Service Worker registered'))
                .catch(err => console.log('Service Worker registration failed'));
        }
    </script>
</body>
</html>
'''

@views_bp.route('/')
def index():
    """Serve the main application."""
    return render_template_string(INDEX_HTML)


# CAP/IPAWS endpoints
@api_bp.route('/cap/status', methods=['GET'])
def cap_status():
    """Check CAP parsing availability."""
    return jsonify({
        'available': CAP_AVAILABLE
    })


@api_bp.route('/cap/parse', methods=['POST'])
def parse_cap_xml():
    """
    Parse CAP XML and return structured data.

    Accepts:
        - JSON with 'xml' field containing CAP XML string
        - Plain text CAP XML (Content-Type: application/xml or text/xml)

    Returns:
        Parsed CAP alert data
    """
    if not CAP_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'CAP parsing not available'
        }), 400

    try:
        if request.content_type and ('xml' in request.content_type or 'text/plain' in request.content_type):
            xml_content = request.get_data(as_text=True)
        else:
            data = request.get_json()
            xml_content = data.get('xml', '')

        if not xml_content:
            return jsonify({
                'success': False,
                'error': 'No CAP XML provided'
            }), 400

        cap = parse_cap(xml_content)

        # serialize CAP to dict
        info_list = []
        for info in cap.info:
            areas = []
            for area in info.areas:
                areas.append({
                    'area_desc': area.area_desc,
                    'polygons': area.polygons,
                    'circles': area.circles,
                    'geocodes': area.geocodes
                })

            info_list.append({
                'language': info.language,
                'categories': [c.value for c in info.categories],
                'event': info.event,
                'response_types': [r.value for r in info.response_types],
                'urgency': info.urgency.value,
                'severity': info.severity.value,
                'certainty': info.certainty.value,
                'event_codes': info.event_codes,
                'effective': info.effective.isoformat() if info.effective else None,
                'onset': info.onset.isoformat() if info.onset else None,
                'expires': info.expires.isoformat() if info.expires else None,
                'sender_name': info.sender_name,
                'headline': info.headline,
                'description': info.description,
                'instruction': info.instruction,
                'areas': areas
            })

        return jsonify({
            'success': True,
            'alert': {
                'identifier': cap.identifier,
                'sender': cap.sender,
                'sent': cap.sent.isoformat(),
                'status': cap.status.value,
                'msg_type': cap.msg_type.value,
                'scope': cap.scope.value,
                'source': cap.source,
                'codes': cap.codes,
                'note': cap.note,
                'info': info_list
            }
        })

    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Parse error: {str(e)}'
        }), 400


@api_bp.route('/cap/to-same', methods=['POST'])
def convert_cap_to_same():
    """
    Convert CAP XML to SAME header.

    Request JSON:
        xml: str - CAP XML content
        callsign: str - Station callsign (optional, default 'EAS-WEB')

    Returns:
        SAME header and optionally encoded audio
    """
    if not CAP_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'CAP parsing not available'
        }), 400

    try:
        data = request.get_json()
        xml_content = data.get('xml', '')
        callsign = data.get('callsign', 'EAS-WEB')
        include_audio = data.get('include_audio', False)

        if not xml_content:
            return jsonify({
                'success': False,
                'error': 'No CAP XML provided'
            }), 400

        cap = parse_cap(xml_content)

        # validate conversion
        validation = validate_cap_for_same(cap)

        if not validation['convertible']:
            return jsonify({
                'success': False,
                'error': 'Cannot convert this CAP to SAME',
                'issues': validation['issues']
            }), 400

        # convert
        same_msg = cap_to_same(cap, callsign=callsign)

        if not same_msg:
            return jsonify({
                'success': False,
                'error': 'Conversion failed'
            }), 400

        result = {
            'success': True,
            'header': same_msg.to_string(),
            'validation_issues': validation['issues'],
            'parsed': {
                'originator': same_msg.originator,
                'event': same_msg.event,
                'event_name': get_event_description(same_msg.event),
                'locations': same_msg.locations,
                'locations_formatted': [format_location_code(loc) for loc in same_msg.locations],
                'purge_time': same_msg.purge_time,
                'issue_time': same_msg.issue_time,
                'callsign': same_msg.callsign
            }
        }

        # optionally generate audio
        if include_audio:
            encoder = SAMEEncoder()
            audio = encoder.encode_full_alert(
                header=same_msg.to_string(),
                attention_duration=8
            )
            wav_bytes = encoder.to_bytes(audio)
            result['audio'] = base64.b64encode(wav_bytes).decode('utf-8')
            result['audio_format'] = 'wav'

        return jsonify(result)

    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Conversion error: {str(e)}'
        }), 400


@api_bp.route('/cap/from-same', methods=['POST'])
def convert_same_to_cap():
    """
    Convert SAME header to CAP XML.

    Request JSON:
        header: str - SAME header string
        sender: str - CAP sender (optional)
        headline: str - Alert headline (optional)
        description: str - Alert description (optional)
        instruction: str - Response instructions (optional)

    Returns:
        CAP XML string
    """
    if not CAP_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'CAP conversion not available'
        }), 400

    try:
        data = request.get_json()
        header = data.get('header', '')

        if not header:
            return jsonify({
                'success': False,
                'error': 'No SAME header provided'
            }), 400

        same_msg = SAMEMessage.parse(header)

        cap_xml = same_to_cap(
            same_msg,
            sender=data.get('sender'),
            headline=data.get('headline'),
            description=data.get('description'),
            instruction=data.get('instruction'),
            area_desc=data.get('area_desc')
        )

        return jsonify({
            'success': True,
            'cap_xml': cap_xml
        })

    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Conversion error: {str(e)}'
        }), 400


@api_bp.route('/cap/validate', methods=['POST'])
def validate_cap():
    """
    Validate CAP XML for SAME conversion compatibility.

    Request JSON:
        xml: str - CAP XML content

    Returns:
        Validation result with issues
    """
    if not CAP_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'CAP validation not available'
        }), 400

    try:
        data = request.get_json()
        xml_content = data.get('xml', '')

        if not xml_content:
            return jsonify({
                'success': False,
                'error': 'No CAP XML provided'
            }), 400

        cap = parse_cap(xml_content)
        validation = validate_cap_for_same(cap)

        return jsonify({
            'success': True,
            'convertible': validation['convertible'],
            'same_event': validation['same_event'],
            'issues': validation['issues']
        })

    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


# NWS Live Feed endpoints
@api_bp.route('/nws/status', methods=['GET'])
def nws_status():
    """Check NWS feed availability."""
    return jsonify({
        'available': NWS_AVAILABLE
    })


@api_bp.route('/nws/alerts', methods=['GET'])
def get_nws_alerts():
    """
    Get active NWS alerts.

    Query params:
        state: str - State code (e.g., TX, CA)
        event: str - Event type filter
        severity: str - Severity filter (Extreme, Severe, Moderate, Minor)
        urgency: str - Urgency filter (Immediate, Expected, Future)
        limit: int - Max alerts to return (default 50)

    Returns:
        List of active alerts
    """
    if not NWS_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'NWS feed not available'
        }), 400

    try:
        client = NWSFeedClient()

        state = request.args.get('state')
        event = request.args.get('event')
        severity = request.args.get('severity')
        urgency = request.args.get('urgency')
        limit = int(request.args.get('limit', 50))

        alerts = client.get_active_alerts(
            area=state,
            event=event,
            severity=severity,
            urgency=urgency,
            limit=limit
        )

        return jsonify({
            'success': True,
            'count': len(alerts),
            'alerts': [alert.to_dict() for alert in alerts]
        })

    except ConnectionError as e:
        return jsonify({
            'success': False,
            'error': f'Connection error: {str(e)}'
        }), 503
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@api_bp.route('/nws/alerts/severe', methods=['GET'])
def get_severe_alerts():
    """Get alerts with Extreme or Severe severity."""
    if not NWS_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'NWS feed not available'
        }), 400

    try:
        client = NWSFeedClient()
        limit = int(request.args.get('limit', 50))
        alerts = client.get_severe_alerts(limit=limit)

        return jsonify({
            'success': True,
            'count': len(alerts),
            'alerts': [alert.to_dict() for alert in alerts]
        })

    except ConnectionError as e:
        return jsonify({
            'success': False,
            'error': f'Connection error: {str(e)}'
        }), 503
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@api_bp.route('/nws/summary', methods=['GET'])
def get_nws_summary():
    """Get summary of current active alerts."""
    if not NWS_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'NWS feed not available'
        }), 400

    try:
        summary = get_alert_summary()
        return jsonify({
            'success': True,
            'summary': summary
        })

    except ConnectionError as e:
        return jsonify({
            'success': False,
            'error': f'Connection error: {str(e)}'
        }), 503
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@api_bp.route('/nws/alert/<path:alert_id>/cap', methods=['GET'])
def get_alert_cap_xml(alert_id):
    """
    Get CAP XML for a specific alert.

    Args:
        alert_id: Alert ID or URL

    Returns:
        CAP XML string
    """
    if not NWS_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'NWS feed not available'
        }), 400

    try:
        client = NWSFeedClient()
        cap_xml = client.get_alert_cap(alert_id)

        if not cap_xml:
            return jsonify({
                'success': False,
                'error': 'Alert not found or CAP unavailable'
            }), 404

        return jsonify({
            'success': True,
            'cap_xml': cap_xml
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@api_bp.route('/nws/alert/<path:alert_id>/same', methods=['GET'])
def convert_nws_to_same(alert_id):
    """
    Convert an NWS alert to SAME format.

    Args:
        alert_id: Alert ID or URL

    Query params:
        callsign: str - Station callsign (default 'NWS-WEB')
        include_audio: bool - Include encoded audio

    Returns:
        SAME header and optionally audio
    """
    if not NWS_AVAILABLE or not CAP_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'NWS feed or CAP conversion not available'
        }), 400

    try:
        client = NWSFeedClient()
        cap_xml = client.get_alert_cap(alert_id)

        if not cap_xml:
            return jsonify({
                'success': False,
                'error': 'Alert not found or CAP unavailable'
            }), 404

        callsign = request.args.get('callsign', 'NWS-WEB')
        include_audio = request.args.get('include_audio', 'false').lower() == 'true'

        cap = parse_cap(cap_xml)
        validation = validate_cap_for_same(cap)

        if not validation['convertible']:
            return jsonify({
                'success': False,
                'error': 'Cannot convert this alert to SAME',
                'issues': validation['issues']
            }), 400

        same_msg = cap_to_same(cap, callsign=callsign)

        if not same_msg:
            return jsonify({
                'success': False,
                'error': 'Conversion failed'
            }), 400

        result = {
            'success': True,
            'header': same_msg.to_string(),
            'validation_issues': validation['issues'],
            'parsed': {
                'originator': same_msg.originator,
                'event': same_msg.event,
                'event_name': get_event_description(same_msg.event),
                'locations': same_msg.locations,
                'locations_formatted': [format_location_code(loc) for loc in same_msg.locations],
                'purge_time': same_msg.purge_time,
                'issue_time': same_msg.issue_time,
                'callsign': same_msg.callsign
            }
        }

        if include_audio:
            encoder = SAMEEncoder()
            audio = encoder.encode_full_alert(
                header=same_msg.to_string(),
                attention_duration=8
            )
            wav_bytes = encoder.to_bytes(audio)
            result['audio'] = base64.b64encode(wav_bytes).decode('utf-8')
            result['audio_format'] = 'wav'

        return jsonify(result)

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

# Batch Processing endpoints
@api_bp.route('/batch/status', methods=['GET'])
def batch_status():
    """Check batch processing availability."""
    return jsonify({
        'available': BATCH_AVAILABLE
    })


@api_bp.route('/batch/upload', methods=['POST'])
def batch_upload():
    """
    Upload batch file (CSV or JSON) for processing.

    Accepts:
        - File upload (multipart/form-data with 'file' field)
        - JSON array directly

    Returns:
        job_id for tracking
    """
    if not BATCH_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Batch processing not available'
        }), 400

    try:
        alerts = []

        if request.content_type and 'multipart/form-data' in request.content_type:
            # file upload
            if 'file' not in request.files:
                return jsonify({
                    'success': False,
                    'error': 'No file provided'
                }), 400

            file = request.files['file']
            content = file.read().decode('utf-8')
            filename = file.filename.lower()

            if filename.endswith('.csv'):
                alerts = parse_csv_batch(content)
            elif filename.endswith('.json'):
                alerts = parse_json_batch(content)
            else:
                return jsonify({
                    'success': False,
                    'error': 'Unsupported file format. Use CSV or JSON.'
                }), 400
        else:
            # JSON array directly
            data = request.get_json()
            if isinstance(data, list):
                import json
                alerts = parse_json_batch(json.dumps(data))
            else:
                return jsonify({
                    'success': False,
                    'error': 'Expected JSON array'
                }), 400

        if not alerts:
            return jsonify({
                'success': False,
                'error': 'No valid alerts found in file'
            }), 400

        # create batch job
        job_id = _batch_processor.create_job(alerts)

        return jsonify({
            'success': True,
            'job_id': job_id,
            'alert_count': len(alerts)
        })

    except ValueError as e:
        return jsonify({
            'success': False,
            'error': f'Parse error: {str(e)}'
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@api_bp.route('/batch/job/<job_id>', methods=['GET'])
def get_batch_job(job_id):
    """
    Get status of a batch job.

    Returns:
        Job status with progress
    """
    if not BATCH_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Batch processing not available'
        }), 400

    try:
        job = _batch_processor.get_job(job_id)

        if not job:
            return jsonify({
                'success': False,
                'error': 'Job not found'
            }), 404

        return jsonify({
            'success': True,
            'job': job.to_dict()
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@api_bp.route('/batch/job/<job_id>/results', methods=['GET'])
def get_batch_results(job_id):
    """
    Get results of a completed batch job.

    Query params:
        offset: int - Result offset (default 0)
        limit: int - Max results (default 100)

    Returns:
        Alert results with audio
    """
    if not BATCH_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Batch processing not available'
        }), 400

    try:
        job = _batch_processor.get_job(job_id)

        if not job:
            return jsonify({
                'success': False,
                'error': 'Job not found'
            }), 404

        offset = int(request.args.get('offset', 0))
        limit = int(request.args.get('limit', 100))

        results_slice = job.results[offset:offset + limit]

        return jsonify({
            'success': True,
            'job_id': job_id,
            'total_results': len(job.results),
            'offset': offset,
            'limit': limit,
            'results': results_slice
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@api_bp.route('/batch/job/<job_id>/start', methods=['POST'])
def start_batch_job(job_id):
    """Start processing a batch job."""
    if not BATCH_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Batch processing not available'
        }), 400

    try:
        _batch_processor.start_job(job_id)

        return jsonify({
            'success': True,
            'job_id': job_id,
            'status': 'processing'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@api_bp.route('/batch/job/<job_id>/cancel', methods=['POST'])
def cancel_batch_job(job_id):
    """Cancel a running batch job."""
    if not BATCH_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Batch processing not available'
        }), 400

    try:
        success = _batch_processor.cancel_job(job_id)

        if not success:
            return jsonify({
                'success': False,
                'error': 'Job not found or already completed'
            }), 404

        return jsonify({
            'success': True,
            'job_id': job_id,
            'status': 'cancelled'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@api_bp.route('/batch/jobs', methods=['GET'])
def list_batch_jobs():
    """List all batch jobs."""
    if not BATCH_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Batch processing not available'
        }), 400

    try:
        jobs = _batch_processor.get_all_jobs()

        return jsonify({
            'success': True,
            'jobs': [job.to_dict() for job in jobs]
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


# Alert Archive endpoints
@api_bp.route('/archive/status', methods=['GET'])
def archive_status():
    """Check archive availability."""
    return jsonify({
        'available': ARCHIVE_AVAILABLE
    })


@api_bp.route('/archive/alerts', methods=['POST'])
def archive_alert():
    """
    Archive an alert.

    Request JSON:
        originator: str
        event: str
        locations: list[str]
        duration: int
        callsign: str
        header: str
        audio: str (optional, base64)
        has_voice: bool (optional)
        metadata: dict (optional)

    Returns:
        alert_id
    """
    if not ARCHIVE_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Archive not available'
        }), 400

    try:
        data = request.get_json()

        audio_data = None
        if 'audio' in data:
            audio_data = base64.b64decode(data['audio'])

        alert_id = _alert_archive.add_alert(
            originator=data['originator'],
            event=data['event'],
            locations=data['locations'],
            duration=data['duration'],
            callsign=data['callsign'],
            header=data['header'],
            audio_data=audio_data,
            has_voice=data.get('has_voice', False),
            metadata=data.get('metadata')
        )

        return jsonify({
            'success': True,
            'alert_id': alert_id
        })

    except KeyError as e:
        return jsonify({
            'success': False,
            'error': f'Missing required field: {str(e)}'
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@api_bp.route('/archive/alerts/<int:alert_id>', methods=['GET'])
def get_archived_alert(alert_id):
    """
    Get archived alert by ID.

    Query params:
        include_audio: bool - Include audio data (default false)

    Returns:
        Alert details
    """
    if not ARCHIVE_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Archive not available'
        }), 400

    try:
        alert = _alert_archive.get_alert(alert_id)

        if not alert:
            return jsonify({
                'success': False,
                'error': 'Alert not found'
            }), 404

        include_audio = request.args.get('include_audio', 'false').lower() == 'true'

        return jsonify({
            'success': True,
            'alert': alert.to_dict(include_audio=include_audio)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@api_bp.route('/archive/alerts', methods=['GET'])
def search_archived_alerts():
    """
    Search archived alerts.

    Query params:
        event: str - Filter by event code
        originator: str - Filter by originator
        location: str - Filter by location code
        start_date: ISO datetime - Start date
        end_date: ISO datetime - End date
        has_voice: bool - Filter by voice presence
        limit: int - Max results (default 100)
        offset: int - Result offset (default 0)

    Returns:
        List of matching alerts
    """
    if not ARCHIVE_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Archive not available'
        }), 400

    try:
        event = request.args.get('event')
        originator = request.args.get('originator')
        location = request.args.get('location')
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))

        start_date = None
        if request.args.get('start_date'):
            start_date = datetime.fromisoformat(request.args.get('start_date'))

        end_date = None
        if request.args.get('end_date'):
            end_date = datetime.fromisoformat(request.args.get('end_date'))

        has_voice = None
        if request.args.get('has_voice'):
            has_voice = request.args.get('has_voice').lower() == 'true'

        alerts = _alert_archive.search_alerts(
            event=event,
            originator=originator,
            location=location,
            start_date=start_date,
            end_date=end_date,
            has_voice=has_voice,
            limit=limit,
            offset=offset
        )

        return jsonify({
            'success': True,
            'count': len(alerts),
            'offset': offset,
            'limit': limit,
            'alerts': [alert.to_dict(include_audio=False) for alert in alerts]
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@api_bp.route('/archive/stats', methods=['GET'])
def archive_stats():
    """Get archive statistics."""
    if not ARCHIVE_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Archive not available'
        }), 400

    try:
        stats = _alert_archive.get_stats()

        return jsonify({
            'success': True,
            'stats': stats
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@api_bp.route('/archive/alerts/<int:alert_id>', methods=['DELETE'])
def delete_archived_alert(alert_id):
    """Delete archived alert."""
    if not ARCHIVE_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Archive not available'
        }), 400

    try:
        success = _alert_archive.delete_alert(alert_id)

        if not success:
            return jsonify({
                'success': False,
                'error': 'Alert not found'
            }), 404

        return jsonify({
            'success': True,
            'alert_id': alert_id
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

# Audio format import with fallback
try:
    from ..audio import AudioConverter, OutputFormat
    AUDIO_CONVERTER_AVAILABLE = True
    _audio_converter = AudioConverter()
except ImportError:
    AUDIO_CONVERTER_AVAILABLE = False
    _audio_converter = None


# Audio Format Conversion endpoints
@api_bp.route('/audio/formats', methods=['GET'])
def get_audio_formats():
    """Get available audio export formats."""
    if not AUDIO_CONVERTER_AVAILABLE:
        formats = ['wav']
        ffmpeg_available = False
    else:
        formats = _audio_converter.get_available_formats()
        ffmpeg_available = _audio_converter.ffmpeg_available

    return jsonify({
        'success': True,
        'formats': formats,
        'ffmpeg_available': ffmpeg_available
    })


@api_bp.route('/audio/convert', methods=['POST'])
def convert_audio_format():
    """
    Convert audio to different format.

    Request JSON:
        audio: str - base64 WAV audio
        format: str - Output format (wav, mp3, ogg, flac)
        bitrate: str (optional) - Bitrate for MP3 (e.g., '192k', '320k')
        quality: int (optional) - Quality for OGG (0-10) or FLAC (0-12)

    Returns:
        Converted audio as base64
    """
    if not AUDIO_CONVERTER_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Audio converter not available'
        }), 400

    try:
        data = request.get_json()
        wav_data = base64.b64decode(data['audio'])
        output_format = OutputFormat(data['format'].lower())

        converted = _audio_converter.convert(
            wav_data,
            output_format,
            bitrate=data.get('bitrate'),
            quality=data.get('quality')
        )

        return jsonify({
            'success': True,
            'audio': base64.b64encode(converted).decode('utf-8'),
            'format': output_format.value
        })

    except KeyError as e:
        return jsonify({
            'success': False,
            'error': f'Missing required field: {str(e)}'
        }), 400
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except RuntimeError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


# OpenAPI/Swagger Documentation
@api_bp.route('/docs/openapi.json', methods=['GET'])
def get_openapi_spec():
    """Generate OpenAPI 3.0 specification."""
    spec = {
        'openapi': '3.0.0',
        'info': {
            'title': 'EAS Webapp API',
            'version': '1.0.0',
            'description': 'API for encoding, decoding, and managing Emergency Alert System (EAS) messages using SAME protocol',
            'contact': {
                'name': 'EAS Webapp',
                'url': 'https://github.com/yourusername/eas-webapp'
            }
        },
        'servers': [
            {
                'url': '/api',
                'description': 'Local development server'
            }
        ],
        'tags': [
            {'name': 'encode', 'description': 'SAME message encoding'},
            {'name': 'decode', 'description': 'SAME message decoding'},
            {'name': 'codes', 'description': 'Reference data (events, originators, locations)'},
            {'name': 'tts', 'description': 'Text-to-speech voice synthesis'},
            {'name': 'cap', 'description': 'CAP/IPAWS parsing and conversion'},
            {'name': 'nws', 'description': 'NWS live alert feed'},
            {'name': 'batch', 'description': 'Batch alert processing'},
            {'name': 'archive', 'description': 'Alert archive with search'},
            {'name': 'audio', 'description': 'Audio format conversion'}
        ],
        'paths': {
            '/encode': {
                'post': {
                    'tags': ['encode'],
                    'summary': 'Encode SAME message to audio',
                    'operationId': 'encodeMessage',
                    'requestBody': {
                        'required': True,
                        'content': {
                            'application/json': {
                                'schema': {
                                    'type': 'object',
                                    'required': ['originator', 'event', 'locations', 'duration', 'callsign'],
                                    'properties': {
                                        'originator': {'type': 'string', 'example': 'WXR'},
                                        'event': {'type': 'string', 'example': 'TOR'},
                                        'locations': {'type': 'array', 'items': {'type': 'string'}, 'example': ['029095']},
                                        'duration': {'type': 'integer', 'example': 30},
                                        'callsign': {'type': 'string', 'example': 'WXYZ/FM'},
                                        'attention_duration': {'type': 'number', 'default': 8}
                                    }
                                }
                            }
                        }
                    },
                    'responses': {
                        '200': {
                            'description': 'Successfully encoded',
                            'content': {
                                'application/json': {
                                    'schema': {
                                        'type': 'object',
                                        'properties': {
                                            'success': {'type': 'boolean'},
                                            'header': {'type': 'string'},
                                            'audio': {'type': 'string', 'format': 'byte'},
                                            'audio_format': {'type': 'string'},
                                            'parsed': {'type': 'object'}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            '/decode': {
                'post': {
                    'tags': ['decode'],
                    'summary': 'Decode SAME message from audio',
                    'operationId': 'decodeMessage',
                    'requestBody': {
                        'required': True,
                        'content': {
                            'multipart/form-data': {
                                'schema': {
                                    'type': 'object',
                                    'properties': {
                                        'audio': {
                                            'type': 'string',
                                            'format': 'binary'
                                        }
                                    }
                                }
                            }
                        }
                    },
                    'responses': {
                        '200': {
                            'description': 'Successfully decoded'
                        }
                    }
                }
            },
            '/codes/events': {
                'get': {
                    'tags': ['codes'],
                    'summary': 'Get all event codes',
                    'operationId': 'getEventCodes',
                    'responses': {
                        '200': {
                            'description': 'Event codes dictionary'
                        }
                    }
                }
            },
            '/nws/alerts': {
                'get': {
                    'tags': ['nws'],
                    'summary': 'Get active NWS alerts',
                    'parameters': [
                        {'name': 'state', 'in': 'query', 'schema': {'type': 'string'}},
                        {'name': 'severity', 'in': 'query', 'schema': {'type': 'string'}},
                        {'name': 'limit', 'in': 'query', 'schema': {'type': 'integer', 'default': 50}}
                    ],
                    'responses': {
                        '200': {
                            'description': 'List of alerts'
                        }
                    }
                }
            }
        },
        'components': {
            'schemas': {
                'SAMEMessage': {
                    'type': 'object',
                    'properties': {
                        'originator': {'type': 'string'},
                        'event': {'type': 'string'},
                        'locations': {'type': 'array', 'items': {'type': 'string'}},
                        'purge_time': {'type': 'string'},
                        'issue_time': {'type': 'string'},
                        'callsign': {'type': 'string'}
                    }
                }
            }
        }
    }

    return jsonify(spec)


@views_bp.route('/docs')
def api_docs():
    """Serve interactive API documentation."""
    html = '''
<!DOCTYPE html>
<html>
<head>
    <title>EAS Webapp API Docs</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
        SwaggerUIBundle({
            url: '/api/docs/openapi.json',
            dom_id: '#swagger-ui',
            deepLinking: true,
            presets: [
                SwaggerUIBundle.presets.apis,
                SwaggerUIBundle.SwaggerUIStandalonePreset
            ]
        });
    </script>
</body>
</html>
    '''
    return render_template_string(html)
