"""
SAME AFSK decoder

Decodes SAME headers from audio using Goertzel algorithm for
efficient single-frequency detection.
"""

import numpy as np
from typing import List, Tuple, Optional
import wave

from .constants import (
    SAMPLE_RATE, BAUD_RATE, BIT_DURATION,
    MARK_FREQ, SPACE_FREQ,
    PREAMBLE_BYTE, HEADER_START, EOM_MARKER
)
from .message import SAMEMessage


class SAMEDecoder:
    """
    Decodes SAME messages from audio.

    Uses Goertzel algorithm for efficient tone detection at
    MARK (2083.3 Hz) and SPACE (1562.5 Hz) frequencies.
    """

    def __init__(self, sample_rate: int = SAMPLE_RATE):
        self.sample_rate = sample_rate
        self.samples_per_bit = int(sample_rate * BIT_DURATION)

        # precompute Goertzel coefficients
        self._mark_coeff = self._goertzel_coeff(MARK_FREQ)
        self._space_coeff = self._goertzel_coeff(SPACE_FREQ)

    def _goertzel_coeff(self, freq: float) -> float:
        """Compute Goertzel coefficient for a target frequency."""
        k = int(0.5 + (self.samples_per_bit * freq / self.sample_rate))
        omega = (2 * np.pi * k) / self.samples_per_bit
        return 2 * np.cos(omega)

    def _goertzel_mag(self, samples: np.ndarray, coeff: float) -> float:
        """
        Compute magnitude at target frequency using Goertzel algorithm.

        More efficient than FFT for single-frequency detection.
        """
        s0, s1, s2 = 0.0, 0.0, 0.0
        for sample in samples:
            s0 = sample + coeff * s1 - s2
            s2 = s1
            s1 = s0

        # magnitude squared (skip sqrt for comparison)
        return s1 * s1 + s2 * s2 - coeff * s1 * s2

    def _detect_bit(self, samples: np.ndarray) -> int:
        """
        Detect whether a bit window contains MARK (1) or SPACE (0).
        """
        mark_mag = self._goertzel_mag(samples, self._mark_coeff)
        space_mag = self._goertzel_mag(samples, self._space_coeff)

        return 1 if mark_mag > space_mag else 0

    def _decode_byte(self, samples: np.ndarray) -> Tuple[int, float]:
        """
        Decode a byte from 8 bit periods of samples.

        Returns:
            Tuple of (byte value, confidence)
        """
        byte_val = 0
        total_confidence = 0

        for i in range(8):
            start = i * self.samples_per_bit
            end = start + self.samples_per_bit
            bit_samples = samples[start:end]

            mark_mag = self._goertzel_mag(bit_samples, self._mark_coeff)
            space_mag = self._goertzel_mag(bit_samples, self._space_coeff)

            bit = 1 if mark_mag > space_mag else 0
            # LSB first
            byte_val |= (bit << i)

            # confidence is ratio of dominant to total
            total = mark_mag + space_mag
            confidence = max(mark_mag, space_mag) / total if total > 0 else 0
            total_confidence += confidence

        return byte_val, total_confidence / 8

    def _find_preamble(self, samples: np.ndarray) -> Optional[int]:
        """
        Search for the preamble pattern (0xAB bytes).

        Returns:
            Sample index where preamble ends, or None if not found
        """
        # slide through looking for consecutive 0xAB bytes
        bytes_per_window = 8  # look for at least 8 preamble bytes
        window_samples = bytes_per_window * 8 * self.samples_per_bit

        step = self.samples_per_bit * 4  # step by half-byte

        for i in range(0, len(samples) - window_samples, step):
            window = samples[i:i + window_samples]

            # try to decode bytes in this window
            preamble_count = 0
            for j in range(bytes_per_window):
                byte_start = j * 8 * self.samples_per_bit
                byte_end = byte_start + 8 * self.samples_per_bit
                byte_samples = window[byte_start:byte_end]

                decoded, confidence = self._decode_byte(byte_samples)
                if decoded == PREAMBLE_BYTE and confidence > 0.6:
                    preamble_count += 1
                else:
                    break

            if preamble_count >= 4:
                # found preamble, return position after it
                return i + preamble_count * 8 * self.samples_per_bit

        return None

    def _decode_string_at(self, samples: np.ndarray, start: int, max_chars: int = 100) -> str:
        """
        Decode ASCII string starting at sample position.

        Stops at end of message marker or max characters.
        """
        result = []
        pos = start

        for _ in range(max_chars):
            if pos + 8 * self.samples_per_bit > len(samples):
                break

            byte_samples = samples[pos:pos + 8 * self.samples_per_bit]
            byte_val, confidence = self._decode_byte(byte_samples)

            if confidence < 0.5:
                # low confidence, probably noise
                break

            # valid ASCII printable range
            if 32 <= byte_val <= 126:
                result.append(chr(byte_val))
            elif byte_val == 0 or byte_val == 255:
                # likely end of message or noise
                break

            pos += 8 * self.samples_per_bit

            # check for end markers
            decoded = ''.join(result)

            # EOM is simple - just NNNN
            if EOM_MARKER in decoded:
                break

            # SAME header format: ZCZC-ORG-EEE-PSSCCC[...]+TTTT-JJJHHMM-LLLLLLLL-
            # Must have: ZCZC, +TTTT (purge time), 7-digit issue time, callsign, trailing dash
            # A complete header has the pattern ending in: -JJJHHMM-CALLSIGN-
            if decoded.startswith('ZCZC') and len(decoded) > 35:
                # check if we have a valid header structure
                # look for pattern: +DDDD-DDDDDDD-XXXXXXXX-$ where D=digit, X=callsign char
                import re
                header_complete = re.search(r'\+\d{4}-\d{7}-[A-Z0-9/\-]{1,8}-$', decoded)
                if header_complete:
                    break

        return ''.join(result)

    def decode(self, samples: np.ndarray) -> List[str]:
        """
        Decode all SAME messages from audio samples.

        Args:
            samples: Audio samples as numpy array

        Returns:
            List of decoded message strings
        """
        messages = []
        pos = 0

        while pos < len(samples):
            # find next preamble
            preamble_end = self._find_preamble(samples[pos:])
            if preamble_end is None:
                break

            actual_pos = pos + preamble_end

            # decode the message following preamble
            message = self._decode_string_at(samples, actual_pos)

            if message:
                # clean up message
                message = message.strip()
                if message.startswith('ZCZC') or message == 'NNNN':
                    if message not in messages:
                        messages.append(message)

            # move past this message
            pos = actual_pos + len(message) * 8 * self.samples_per_bit + self.samples_per_bit * 8

        return messages

    def decode_file(self, filename: str) -> List[str]:
        """
        Decode SAME messages from a WAV file.

        Args:
            filename: Path to WAV file or file-like object

        Returns:
            List of decoded message strings
        """
        with wave.open(filename, 'r') as wav:
            n_channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            framerate = wav.getframerate()
            n_frames = wav.getnframes()

            raw = wav.readframes(n_frames)

            # convert to numpy array
            if sample_width == 1:
                dtype = np.uint8
                samples = np.frombuffer(raw, dtype=dtype).astype(np.float64)
                samples = (samples - 128) / 128
            elif sample_width == 2:
                dtype = np.int16
                samples = np.frombuffer(raw, dtype=dtype).astype(np.float64)
                samples = samples / 32768
            elif sample_width == 3:
                # 24-bit PCM (less common)
                samples = np.frombuffer(raw, dtype=np.uint8).astype(np.float64)
                samples = samples.reshape(-1, 3)
                # convert 24-bit to 32-bit integer
                samples = (samples[:, 2].astype(np.int32) << 16) | (samples[:, 1].astype(np.int32) << 8) | samples[:, 0].astype(np.int32)
                samples = samples.astype(np.float64) / (2**23)
            elif sample_width == 4:
                # 32-bit PCM (common in modern audio software)
                dtype = np.int32
                samples = np.frombuffer(raw, dtype=dtype).astype(np.float64)
                samples = samples / (2**31)
            else:
                raise ValueError(f"Unsupported sample width: {sample_width}")

            # convert to mono if stereo
            if n_channels == 2:
                samples = samples.reshape(-1, 2).mean(axis=1)
            elif n_channels > 2:
                # mix down multi-channel to mono
                samples = samples.reshape(-1, n_channels).mean(axis=1)

            # resample if needed
            if framerate != self.sample_rate:
                # simple resampling
                ratio = self.sample_rate / framerate
                new_length = int(len(samples) * ratio)
                indices = np.linspace(0, len(samples) - 1, new_length)
                samples = np.interp(indices, np.arange(len(samples)), samples)

        return self.decode(samples)

    def decode_bytes(self, audio_bytes: bytes) -> List[str]:
        """
        Decode SAME messages from audio bytes.

        Supports WAV, Opus, MP3, and other formats by attempting decode.
        If the file isn't a WAV, tries to convert it first.

        Args:
            audio_bytes: Audio file as bytes

        Returns:
            List of decoded message strings
        """
        import io
        buffer = io.BytesIO(audio_bytes)

        # try to decode as WAV first
        try:
            return self.decode_file(buffer)
        except (wave.Error, EOFError, RuntimeError) as e:
            pass

        # if WAV decode fails, try to convert from other formats
        try:
            from pydub import AudioSegment
            buffer.seek(0)

            # try to detect format and convert
            audio = None
            buffer.seek(0)
            try:
                audio = AudioSegment.from_opus(io.BytesIO(audio_bytes))
            except Exception:
                pass

            if not audio:
                buffer.seek(0)
                try:
                    audio = AudioSegment.from_mp3(io.BytesIO(audio_bytes))
                except Exception:
                    pass

            if not audio:
                buffer.seek(0)
                try:
                    audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
                except Exception:
                    pass

            if audio:
                # convert to WAV bytes
                wav_buffer = io.BytesIO()
                audio.export(wav_buffer, format="wav")
                wav_buffer.seek(0)
                return self.decode_file(wav_buffer)
        except ImportError:
            pass

        # if all else fails, raise the original error
        raise ValueError("Could not decode audio file. Ensure it's a valid WAV, MP3, or Opus file. Install pydub for format conversion support.")

    def decode_to_message(self, samples: np.ndarray) -> Optional[SAMEMessage]:
        """
        Decode audio and return a SAMEMessage object.

        Returns first valid header found, or None.
        """
        messages = self.decode(samples)

        for msg in messages:
            if msg.startswith('ZCZC'):
                try:
                    return SAMEMessage.parse(msg)
                except ValueError:
                    continue

        return None
