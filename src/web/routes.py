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
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EAS Webapp</title>
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
    <div id="app"></div>
    <script src="/static/js/app.js"></script>
</body>
</html>
'''

@views_bp.route('/')
def index():
    """Serve the main application."""
    return render_template_string(INDEX_HTML)
