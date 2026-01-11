"""
TTS Synthesizer for EAS voice messages

Supports multiple backends:
- edge-tts: Microsoft Edge TTS (free, high quality, recommended)
- pyttsx3: Offline system TTS (fallback)

Edge TTS provides access to natural-sounding voices similar to
what modern EAS encoders use, vs the robotic Microsoft Sam era.
"""

import asyncio
import numpy as np
from enum import Enum
from typing import Optional
import wave
import io
import tempfile
import os

from ..same.constants import SAMPLE_RATE


class VoiceStyle(Enum):
    """Preset voice styles for EAS messages."""
    # Authoritative male voices
    MALE_AUTHORITATIVE = 'en-US-GuyNeural'
    MALE_NEWSCAST = 'en-US-ChristopherNeural'

    # Authoritative female voices
    FEMALE_AUTHORITATIVE = 'en-US-JennyNeural'
    FEMALE_NEWSCAST = 'en-US-AriaNeural'

    # Classic robotic (for the purists)
    MALE_ROBOTIC = 'en-US-DavisNeural'

    # Default
    DEFAULT = 'en-US-GuyNeural'


class TTSSynthesizer:
    """
    Synthesize voice messages for EAS alerts.

    Uses edge-tts by default for high-quality voices.
    Falls back to pyttsx3 if edge-tts unavailable.
    """

    def __init__(self, voice: VoiceStyle = VoiceStyle.DEFAULT, sample_rate: int = SAMPLE_RATE):
        self.voice = voice
        self.sample_rate = sample_rate
        self._backend = self._detect_backend()

    def _detect_backend(self) -> str:
        """Detect available TTS backend."""
        try:
            import edge_tts
            return 'edge'
        except ImportError:
            pass

        try:
            import pyttsx3
            return 'pyttsx3'
        except ImportError:
            pass

        return 'none'

    async def synthesize_async(self, text: str) -> np.ndarray:
        """
        Synthesize text to audio (async).

        Args:
            text: Text to synthesize

        Returns:
            Audio samples as numpy array
        """
        if self._backend == 'edge':
            return await self._synthesize_edge(text)
        elif self._backend == 'pyttsx3':
            return self._synthesize_pyttsx3(text)
        else:
            raise RuntimeError("No TTS backend available. Install edge-tts or pyttsx3.")

    def synthesize(self, text: str) -> np.ndarray:
        """
        Synthesize text to audio (sync wrapper).

        Args:
            text: Text to synthesize

        Returns:
            Audio samples as numpy array
        """
        if self._backend == 'edge':
            return asyncio.run(self._synthesize_edge(text))
        elif self._backend == 'pyttsx3':
            return self._synthesize_pyttsx3(text)
        else:
            raise RuntimeError("No TTS backend available. Install edge-tts or pyttsx3.")

    async def _synthesize_edge(self, text: str) -> np.ndarray:
        """Synthesize using edge-tts."""
        import edge_tts

        # edge-tts outputs mp3, we need to convert to wav
        communicate = edge_tts.Communicate(text, self.voice.value)

        # collect audio chunks
        audio_data = b''
        async for chunk in communicate.stream():
            if chunk['type'] == 'audio':
                audio_data += chunk['data']

        # convert mp3 to wav using temp file
        # edge-tts outputs mp3, need to decode
        samples = self._decode_mp3(audio_data)

        # resample to target sample rate if needed
        return self._resample(samples, 24000, self.sample_rate)

    def _decode_mp3(self, mp3_data: bytes) -> np.ndarray:
        """Decode MP3 data to numpy array."""
        try:
            # try pydub if available
            from pydub import AudioSegment
            audio = AudioSegment.from_mp3(io.BytesIO(mp3_data))
            samples = np.array(audio.get_array_of_samples(), dtype=np.float64)
            samples = samples / 32768.0
            if audio.channels == 2:
                samples = samples.reshape(-1, 2).mean(axis=1)
            return samples
        except ImportError:
            pass

        # fallback: use ffmpeg via subprocess
        import subprocess
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            f.write(mp3_data)
            mp3_path = f.name

        wav_path = mp3_path.replace('.mp3', '.wav')

        try:
            subprocess.run([
                'ffmpeg', '-y', '-i', mp3_path,
                '-ar', '24000', '-ac', '1', '-f', 'wav', wav_path
            ], capture_output=True, check=True)

            with wave.open(wav_path, 'r') as wav:
                raw = wav.readframes(wav.getnframes())
                samples = np.frombuffer(raw, dtype=np.int16).astype(np.float64)
                samples = samples / 32768.0

            return samples
        finally:
            os.unlink(mp3_path)
            if os.path.exists(wav_path):
                os.unlink(wav_path)

    def _synthesize_pyttsx3(self, text: str) -> np.ndarray:
        """Synthesize using pyttsx3 (offline)."""
        import pyttsx3

        engine = pyttsx3.init()

        # adjust voice settings for EAS-appropriate delivery
        engine.setProperty('rate', 150)  # slightly slower for clarity

        # save to temp file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            wav_path = f.name

        try:
            engine.save_to_file(text, wav_path)
            engine.runAndWait()

            with wave.open(wav_path, 'r') as wav:
                raw = wav.readframes(wav.getnframes())
                file_rate = wav.getframerate()
                samples = np.frombuffer(raw, dtype=np.int16).astype(np.float64)
                samples = samples / 32768.0

                if wav.getnchannels() == 2:
                    samples = samples.reshape(-1, 2).mean(axis=1)

            return self._resample(samples, file_rate, self.sample_rate)
        finally:
            os.unlink(wav_path)

    def _resample(self, samples: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
        """Simple linear resampling."""
        if source_rate == target_rate:
            return samples

        ratio = target_rate / source_rate
        new_length = int(len(samples) * ratio)
        indices = np.linspace(0, len(samples) - 1, new_length)
        return np.interp(indices, np.arange(len(samples)), samples)

    def generate_eas_announcement(
        self,
        event_name: str,
        locations: list[str],
        originator: str,
        callsign: str
    ) -> np.ndarray:
        """
        Generate a standard EAS voice announcement.

        Args:
            event_name: Human-readable event name (e.g., "Tornado Warning")
            locations: List of human-readable location names
            originator: Originator name (e.g., "National Weather Service")
            callsign: Station callsign

        Returns:
            Audio samples as numpy array
        """
        # standard EAS announcement format
        locations_text = ', '.join(locations)

        text = (
            f"The following message is transmitted at the request of {originator}. "
            f"A {event_name} has been issued for {locations_text}. "
            f"This is {callsign}."
        )

        return self.synthesize(text)

    @property
    def available(self) -> bool:
        """Check if TTS is available."""
        return self._backend != 'none'

    @property
    def backend_name(self) -> str:
        """Get name of active TTS backend."""
        return self._backend
