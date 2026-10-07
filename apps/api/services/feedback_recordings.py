"""Bounded audio validation/conversion and local whisper.cpp transcription."""
import io
from pathlib import Path
import subprocess
import tempfile
import wave

from fastapi import HTTPException

from ..config import settings


AUDIO_TYPES = {'audio/webm': 'webm', 'audio/ogg': 'ogg', 'audio/mp4': 'mp4',
               'audio/wav': 'wav', 'audio/x-wav': 'wav'}


def validate_container(data: bytes, content_type: str) -> str:
    kind = AUDIO_TYPES.get(content_type.split(';')[0].strip().lower())
    signatures = {
        'webm': data.startswith(b'\x1aE\xdf\xa3'),
        'ogg': data.startswith(b'OggS'),
        'mp4': len(data) >= 12 and data[4:8] == b'ftyp',
        'wav': data.startswith(b'RIFF') and data[8:12] == b'WAVE',
    }
    if not kind or not signatures[kind]:
        raise HTTPException(415, 'Use a WebM, Ogg, MP4 or WAV audio recording')
    return kind


def normalize_audio(data: bytes) -> bytes:
    # Fixed filenames, no shell, restricted protocols/demuxers and bounded output.
    # Decode one extra second to reject overlong audio rather than silently trim it.
    with tempfile.TemporaryDirectory(prefix='feedback-audio-') as directory:
        source, target = Path(directory) / 'input', Path(directory) / 'output.wav'
        source.write_bytes(data)
        try:
            subprocess.run([
                'ffmpeg', '-nostdin', '-v', 'error', '-y',
                '-protocol_whitelist', 'file,pipe', '-format_whitelist', 'matroska,webm,ogg,mov,wav',
                '-i', str(source), '-map', '0:a:0', '-vn',
                '-t', str(settings.product_feedback_audio_max_seconds + 1),
                '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(target),
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=settings.product_feedback_audio_timeout_seconds)
        except FileNotFoundError as exc:
            raise HTTPException(503, 'Audio processing is unavailable') from exc
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise HTTPException(422, 'Audio could not be processed') from exc
        converted = target.read_bytes()
        with wave.open(io.BytesIO(converted)) as audio:
            duration = audio.getnframes() / audio.getframerate()
        if duration <= 0 or duration > settings.product_feedback_audio_max_seconds:
            raise HTTPException(422, 'Recording exceeds the duration limit or is empty')
        return converted


def transcribe_audio(data: bytes) -> str:
    # Same open local engine used by OpenWhispr; no desktop app or cloud key.
    # Only trusted server configuration supplies binary/model paths. No shell.
    with tempfile.TemporaryDirectory(prefix='feedback-whisper-') as directory:
        source = Path(directory) / 'audio.wav'
        output = Path(directory) / 'transcript'
        source.write_bytes(normalize_audio(data))
        subprocess.run([
            settings.product_feedback_whisper_binary,
            '-m', settings.product_feedback_whisper_model,
            '-f', str(source), '-l', 'auto', '-otxt', '-of', str(output),
            '-t', str(settings.product_feedback_whisper_threads), '-ng',
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=settings.product_feedback_audio_timeout_seconds)
        with output.with_suffix('.txt').open(encoding='utf-8') as transcript:
            raw = transcript.read(16001)
            if len(raw) > 16000:
                raise ValueError('Transcript exceeds feedback limit')
            text = raw.strip()
    if not text or len(text) > 4000:
        raise ValueError('No usable transcript returned')
    return text
