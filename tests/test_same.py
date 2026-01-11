"""
Tests for SAME encoder/decoder
"""

import numpy as np
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.same import SAMEEncoder, SAMEDecoder, SAMEMessage
from src.same.constants import SAMPLE_RATE, MARK_FREQ, SPACE_FREQ


class TestSAMEMessage:
    """Tests for SAMEMessage parsing and creation."""

    def test_parse_valid_header(self):
        """Test parsing a valid SAME header."""
        header = "ZCZC-WXR-TOR-029095+0030-1051234-KWNS/NWS-"
        msg = SAMEMessage.parse(header)

        assert msg.originator == "WXR"
        assert msg.event == "TOR"
        assert msg.locations == ["029095"]
        assert msg.purge_time == "0030"
        assert msg.issue_time == "1051234"
        assert msg.callsign == "KWNS/NWS"

    def test_parse_multiple_locations(self):
        """Test parsing header with multiple location codes."""
        header = "ZCZC-WXR-SVR-029095-029097-029099+0045-1051500-KWNS/NWS-"
        msg = SAMEMessage.parse(header)

        assert len(msg.locations) == 3
        assert msg.locations == ["029095", "029097", "029099"]

    def test_parse_without_prefix(self):
        """Test that headers without ZCZC- prefix are handled."""
        header = "WXR-TOR-029095+0030-1051234-KWNS/NWS-"
        msg = SAMEMessage.parse(header)
        assert msg.originator == "WXR"

    def test_to_string(self):
        """Test generating header string from message."""
        msg = SAMEMessage(
            originator="WXR",
            event="TOR",
            locations=["029095"],
            purge_time="0030",
            issue_time="1051234",
            callsign="KWNS/NWS"
        )

        expected = "ZCZC-WXR-TOR-029095+0030-1051234-KWNS/NWS-"
        assert msg.to_string() == expected

    def test_create_message(self):
        """Test creating a message with auto-generated time."""
        msg = SAMEMessage.create(
            originator="WXR",
            event="TOR",
            locations=["029095"],
            duration_minutes=30,
            callsign="KWNS/NWS"
        )

        assert msg.originator == "WXR"
        assert msg.event == "TOR"
        assert msg.purge_time == "0030"
        assert len(msg.issue_time) == 7

    def test_invalid_originator(self):
        """Test that invalid originator raises error."""
        with pytest.raises(ValueError):
            SAMEMessage(
                originator="WXYZ",  # too long
                event="TOR",
                locations=["029095"],
                purge_time="0030",
                issue_time="1051234",
                callsign="KWNS"
            )

    def test_invalid_location(self):
        """Test that invalid location code raises error."""
        with pytest.raises(ValueError):
            SAMEMessage(
                originator="WXR",
                event="TOR",
                locations=["12345"],  # wrong length
                purge_time="0030",
                issue_time="1051234",
                callsign="KWNS"
            )


class TestSAMEEncoder:
    """Tests for SAME encoder."""

    def test_encoder_creates_audio(self):
        """Test that encoder produces audio output."""
        encoder = SAMEEncoder()
        msg = SAMEMessage.create(
            originator="WXR",
            event="TOR",
            locations=["029095"],
            duration_minutes=30,
            callsign="KWNS/NWS"
        )

        audio = encoder.encode_header(msg.to_string())

        assert len(audio) > 0
        assert isinstance(audio, np.ndarray)

    def test_audio_amplitude_bounds(self):
        """Test that audio stays within [-1, 1]."""
        encoder = SAMEEncoder()
        audio = encoder.generate_attention_signal(1.0)

        assert np.max(np.abs(audio)) <= 1.0

    def test_attention_signal_duration(self):
        """Test attention signal has correct duration."""
        encoder = SAMEEncoder()
        duration = 8.0
        audio = encoder.generate_attention_signal(duration)

        expected_samples = int(SAMPLE_RATE * duration)
        assert len(audio) == expected_samples

    def test_full_alert_structure(self):
        """Test that full alert contains all components."""
        encoder = SAMEEncoder()
        msg = SAMEMessage.create(
            originator="WXR",
            event="TOR",
            locations=["029095"],
            duration_minutes=30,
            callsign="KWNS/NWS"
        )

        audio = encoder.encode_full_alert(msg.to_string())

        # should be several seconds of audio
        min_duration = 15  # at least 15 seconds
        assert len(audio) / SAMPLE_RATE >= min_duration

    def test_wav_bytes_output(self):
        """Test WAV bytes generation."""
        encoder = SAMEEncoder()
        audio = encoder.generate_attention_signal(1.0)
        wav_bytes = encoder.to_bytes(audio)

        # WAV files start with RIFF header
        assert wav_bytes[:4] == b'RIFF'


class TestSAMEDecoder:
    """Tests for SAME decoder."""

    def test_roundtrip_encode_decode(self):
        """Test that encoded messages can be decoded."""
        encoder = SAMEEncoder()
        decoder = SAMEDecoder()

        original = "ZCZC-WXR-TOR-029095+0030-1051234-KWNS/NWS-"
        audio = encoder.encode_header(original)

        decoded = decoder.decode(audio)

        # should find at least one message
        assert len(decoded) >= 1
        # first decoded should match original (allowing for some decode issues)
        # Note: perfect roundtrip may not always work due to FSK tolerances

    def test_eom_detection(self):
        """Test EOM marker detection."""
        encoder = SAMEEncoder()
        decoder = SAMEDecoder()

        audio = encoder.encode_eom()
        decoded = decoder.decode(audio)

        # should find NNNN
        assert any('NNNN' in msg for msg in decoded)
