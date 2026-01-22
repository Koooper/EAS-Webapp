"""
Audio format converter using pydub/ffmpeg.
"""

import io
import subprocess
import tempfile
import os
from enum import Enum
from typing import Optional


class OutputFormat(Enum):
    """Supported output formats."""
    WAV = 'wav'
    MP3 = 'mp3'
    OGG = 'ogg'
    FLAC = 'flac'


class AudioConverter:
    """
    Convert WAV audio to various formats.

    Uses ffmpeg if available, falls back to basic WAV only.
    """

    def __init__(self):
        """Initialize converter and check ffmpeg availability."""
        self.ffmpeg_available = self._check_ffmpeg()

    def _check_ffmpeg(self) -> bool:
        """Check if ffmpeg is available."""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def convert(
        self,
        wav_data: bytes,
        output_format: OutputFormat,
        bitrate: Optional[str] = None,
        quality: Optional[int] = None
    ) -> bytes:
        """
        Convert WAV audio to specified format.

        Args:
            wav_data: Input WAV audio bytes
            output_format: Target format
            bitrate: Bitrate for lossy formats (e.g., '192k', '320k')
            quality: Quality level for OGG (0-10, 10=highest)

        Returns:
            Converted audio bytes

        Raises:
            RuntimeError: If ffmpeg not available for non-WAV formats
            ValueError: If conversion fails
        """
        if output_format == OutputFormat.WAV:
            return wav_data

        if not self.ffmpeg_available:
            raise RuntimeError(
                'ffmpeg not available. Install ffmpeg for MP3/OGG/FLAC export.'
            )

        # write input to temp file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as input_file:
            input_path = input_file.name
            input_file.write(wav_data)

        # output temp file
        output_suffix = f'.{output_format.value}'
        with tempfile.NamedTemporaryFile(suffix=output_suffix, delete=False) as output_file:
            output_path = output_file.name

        try:
            # build ffmpeg command
            cmd = ['ffmpeg', '-y', '-i', input_path]

            if output_format == OutputFormat.MP3:
                # MP3 encoding
                if bitrate:
                    cmd.extend(['-b:a', bitrate])
                else:
                    cmd.extend(['-q:a', '2'])  # VBR quality ~190kbps
                cmd.extend(['-codec:a', 'libmp3lame'])

            elif output_format == OutputFormat.OGG:
                # OGG Vorbis encoding
                if quality is not None:
                    cmd.extend(['-q:a', str(quality)])
                else:
                    cmd.extend(['-q:a', '6'])  # quality ~192kbps
                cmd.extend(['-codec:a', 'libvorbis'])

            elif output_format == OutputFormat.FLAC:
                # FLAC lossless encoding
                cmd.extend(['-codec:a', 'flac'])
                if quality is not None:
                    cmd.extend(['-compression_level', str(min(quality, 12))])

            cmd.append(output_path)

            # run conversion
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=30
            )

            if result.returncode != 0:
                error_msg = result.stderr.decode('utf-8', errors='ignore')
                raise ValueError(f'Conversion failed: {error_msg}')

            # read output
            with open(output_path, 'rb') as f:
                return f.read()

        finally:
            # cleanup temp files
            try:
                os.unlink(input_path)
            except:
                pass
            try:
                os.unlink(output_path)
            except:
                pass

    def get_available_formats(self) -> list:
        """Get list of available output formats."""
        if self.ffmpeg_available:
            return [fmt.value for fmt in OutputFormat]
        else:
            return [OutputFormat.WAV.value]
