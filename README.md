# EAS-Webapp

A webapp for creating, decoding, and testing emergency warning messages using SAME (Specific Area Message Encoding) per [47 CFR 11.31](https://www.ecfr.gov/current/title-47/chapter-I/subchapter-A/part-11/subpart-B/section-11.31).

Built for the EAS YouTube community tired of decades-old encoders and Microsoft Sam TTS.

## Features

- **SAME Encoder**: Generates spec-compliant AFSK audio (preamble, 3x header repetition, attention tone, EOM)
- **SAME Decoder**: Extracts headers from audio using Goertzel frequency detection
- **TTS Voice**: Microsoft Edge neural voices via edge-tts (not the robotic garbage)
- **Web UI**: Terminal-aesthetic interface for encoding/decoding alerts
- **Reference Data**: Full event codes, originators, and FIPS state codes from 47 CFR 11.31

## Quick Start

```bash
# clone
git clone https://github.com/yourusername/EAS-Webapp.git
cd EAS-Webapp

# setup
python -m venv venv
./venv/Scripts/pip install -r requirements.txt  # windows
# or: ./venv/bin/pip install -r requirements.txt  # linux/mac

# run
./venv/Scripts/python run.py  # windows
# or: ./venv/bin/python run.py  # linux/mac

# open http://127.0.0.1:5000
```

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/encode` | POST | Encode SAME message to audio |
| `/api/encode/with-voice` | POST | Encode with TTS voice message |
| `/api/encode/header-only` | POST | Encode header burst only |
| `/api/decode` | POST | Decode audio file to SAME headers |
| `/api/parse` | POST | Parse SAME header string |
| `/api/codes/events` | GET | List all event codes |
| `/api/codes/originators` | GET | List originator codes |
| `/api/codes/states` | GET | List state FIPS codes |
| `/api/tts/status` | GET | Check TTS availability |

### Encode Example

```bash
curl -X POST http://127.0.0.1:5000/api/encode \
  -H "Content-Type: application/json" \
  -d '{
    "originator": "WXR",
    "event": "TOR",
    "locations": ["029095"],
    "duration": 30,
    "callsign": "KWNS/NWS"
  }'
```

## SAME Protocol

Per 47 CFR 11.31:

- **AFSK**: Mark = 2083.3 Hz (1), Space = 1562.5 Hz (0)
- **Baud**: 520.83 bps
- **Preamble**: 16 bytes of 0xAB (LSB-first)
- **Header**: `ZCZC-ORG-EEE-PSSCCC+TTTT-JJJHHMM-LLLLLLLL-`
- **Transmission**: Header sent 3x with 1-second gaps
- **Attention**: 853 Hz + 960 Hz dual tone, 8-25 seconds
- **EOM**: `NNNN` sent 3x with preambles

## Project Structure

```
src/
├── same/           # SAME protocol (encoder, decoder, message parsing)
├── eas/            # Reference data (event codes, originators, FIPS)
├── tts/            # Text-to-speech synthesis
└── web/            # Flask API + routes
static/
├── css/            # Terminal aesthetic
└── js/             # Frontend app
```

## Dependencies

- numpy - audio signal generation
- flask - web backend
- edge-tts - Microsoft neural TTS (optional but recommended)
- pydub - audio format conversion

## Future

- CAP/IPAWS XML parsing
- WEA message rendering (phone UI mockup)
- Full FIPS county database
- Audio waveform visualization

## License

MIT
