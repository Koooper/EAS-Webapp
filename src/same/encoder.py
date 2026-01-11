"""
SAME AFSK encoder per 47 CFR 11.31

Generates audio-frequency shift keying signals for SAME headers.
"""

import numpy as np
from typing import Optional
import wave
import struct

from .constants import (
    SAMPLE_RATE, BAUD_RATE, BIT_DURATION,
    MARK_FREQ, SPACE_FREQ,
    ATTENTION_FREQ_1, ATTENTION_FREQ_2, ATTENTION_DURATION_DEFAULT,
    PREAMBLE_BYTES, PREAMBLE_BYTE,
    HEADER_REPETITIONS, HEADER_GAP, EOM_REPETITIONS,
    HEADER_START, EOM_MARKER,
    TONE_AMPLITUDE
)


class SAMEEncoder:
    """
    Encodes SAME messages to audio per FCC specifications.

    The complete EAS audio structure:
    1. Preamble (16 bytes of 0xAB) + Header string, repeated 3x with 1s gaps
    2. Attention signal (853 Hz + 960 Hz dual tone)
    3. [Voice/audio message - not generated here]
    4. Preamble + EOM (NNNN), repeated 3x with 1s gaps
    """

    def __init__(self, sample_rate: int = SAMPLE_RATE):
        self.sample_rate = sample_rate
        self.samples_per_bit = int(sample_rate * BIT_DURATION)
        # phase tracking for continuous wave generation
        self._phase = 0.0

    def _generate_tone(self, frequency: float, duration: float) -> np.ndarray:
        """Generate a sine wave tone with phase continuity."""
        n_samples = int(self.sample_rate * duration)
        t = np.arange(n_samples) / self.sample_rate
        signal = TONE_AMPLITUDE * np.sin(2 * np.pi * frequency * t + self._phase)
        # update phase for continuity
        self._phase = (self._phase + 2 * np.pi * frequency * duration) % (2 * np.pi)
        return signal

    def _generate_fsk_bit(self, bit: int) -> np.ndarray:
        """Generate FSK signal for a single bit."""
        freq = MARK_FREQ if bit else SPACE_FREQ
        return self._generate_tone(freq, BIT_DURATION)

    def _generate_fsk_byte(self, byte: int) -> np.ndarray:
        """
        Generate FSK signal for a byte.
        SAME uses LSB-first transmission.
        """
        signal = np.array([], dtype=np.float64)
        for i in range(8):
            bit = (byte >> i) & 1
            signal = np.concatenate([signal, self._generate_fsk_bit(bit)])
        return signal

    def _generate_preamble(self) -> np.ndarray:
        """Generate the 16-byte preamble (0xAB pattern)."""
        signal = np.array([], dtype=np.float64)
        for _ in range(PREAMBLE_BYTES):
            signal = np.concatenate([signal, self._generate_fsk_byte(PREAMBLE_BYTE)])
        return signal

    def _generate_string(self, text: str) -> np.ndarray:
        """Generate FSK signal for an ASCII string."""
        signal = np.array([], dtype=np.float64)
        for char in text:
            signal = np.concatenate([signal, self._generate_fsk_byte(ord(char))])
        return signal

    def _generate_silence(self, duration: float) -> np.ndarray:
        """Generate silence for the specified duration."""
        return np.zeros(int(self.sample_rate * duration))

    def generate_attention_signal(self, duration: float = ATTENTION_DURATION_DEFAULT) -> np.ndarray:
        """
        Generate the two-tone attention signal.
        853 Hz + 960 Hz combined at equal amplitude.
        """
        n_samples = int(self.sample_rate * duration)
        t = np.arange(n_samples) / self.sample_rate
        tone1 = np.sin(2 * np.pi * ATTENTION_FREQ_1 * t)
        tone2 = np.sin(2 * np.pi * ATTENTION_FREQ_2 * t)
        # combine at half amplitude each to prevent clipping
        return TONE_AMPLITUDE * (tone1 + tone2) / 2

    def encode_header(self, message: str) -> np.ndarray:
        """
        Encode a SAME header string to audio.

        The header is transmitted 3 times with 1-second gaps.
        Each transmission includes the preamble.

        Args:
            message: Full SAME header (e.g., "ZCZC-WXR-TOR-029095+0030-1051234-KWNS/NWS-")

        Returns:
            numpy array of audio samples
        """
        # ensure message starts with ZCZC
        if not message.startswith(HEADER_START):
            message = f"{HEADER_START}-{message}"

        signal = np.array([], dtype=np.float64)

        for i in range(HEADER_REPETITIONS):
            self._phase = 0.0  # reset phase for each burst
            preamble = self._generate_preamble()
            header = self._generate_string(message)
            signal = np.concatenate([signal, preamble, header])

            if i < HEADER_REPETITIONS - 1:
                signal = np.concatenate([signal, self._generate_silence(HEADER_GAP)])

        return signal

    def encode_eom(self) -> np.ndarray:
        """
        Encode the End of Message marker.

        EOM (NNNN) is transmitted 3 times with 1-second gaps,
        each with preamble.
        """
        signal = np.array([], dtype=np.float64)

        for i in range(EOM_REPETITIONS):
            self._phase = 0.0
            preamble = self._generate_preamble()
            eom = self._generate_string(EOM_MARKER)
            signal = np.concatenate([signal, preamble, eom])

            if i < EOM_REPETITIONS - 1:
                signal = np.concatenate([signal, self._generate_silence(HEADER_GAP)])

        return signal

    def encode_full_alert(
        self,
        header: str,
        attention_duration: float = ATTENTION_DURATION_DEFAULT,
        voice_audio: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """
        Generate a complete EAS alert audio sequence.

        Structure:
        1. Header burst (3x with preambles)
        2. Attention signal
        3. Voice message (optional)
        4. EOM burst (3x with preambles)

        Args:
            header: SAME header string
            attention_duration: Duration of attention signal in seconds
            voice_audio: Optional voice/audio message samples

        Returns:
            Complete alert audio as numpy array
        """
        signal = self.encode_header(header)
        signal = np.concatenate([signal, self._generate_silence(1.0)])
        signal = np.concatenate([signal, self.generate_attention_signal(attention_duration)])

        if voice_audio is not None:
            signal = np.concatenate([signal, self._generate_silence(0.5)])
            signal = np.concatenate([signal, voice_audio])
            signal = np.concatenate([signal, self._generate_silence(0.5)])
        else:
            signal = np.concatenate([signal, self._generate_silence(1.0)])

        signal = np.concatenate([signal, self.encode_eom()])

        return signal

    def to_wav(self, samples: np.ndarray, filename: str):
        """Export audio samples to a WAV file."""
        # convert to 16-bit PCM
        samples_int = np.int16(samples * 32767)

        with wave.open(filename, 'w') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)  # 16-bit
            wav.setframerate(self.sample_rate)
            wav.writeframes(samples_int.tobytes())

    def to_bytes(self, samples: np.ndarray) -> bytes:
        """Convert audio samples to WAV bytes (for web streaming)."""
        import io
        samples_int = np.int16(samples * 32767)

        buffer = io.BytesIO()
        with wave.open(buffer, 'w') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(self.sample_rate)
            wav.writeframes(samples_int.tobytes())

        buffer.seek(0)
        return buffer.read()
