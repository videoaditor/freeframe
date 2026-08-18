"""
Tests for FFmpegTranscoder: command construction and error handling.

Verifies:
- has_audio=True  → ffmpeg cmd includes -map a:0, var_stream_map has audio tracks
- has_audio=False → ffmpeg cmd excludes -map a:0, var_stream_map is video-only
- _run() uses errors='replace' to survive Latin-1/Shift-JIS metadata
- _run() raises RuntimeError with stderr on non-zero exit
"""
import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

from packages.transcoder.ffmpeg_transcoder import FFmpegTranscoder
from packages.transcoder.base import TranscodeJob


def _make_job(qualities: list[str] | None = None) -> TranscodeJob:
    return TranscodeJob(
        media_id="media-1",
        version_id="v1",
        input_s3_key="uploads/video.mp4",
        output_s3_prefix="hls/media-1/v1",
        qualities=qualities or ["1080p", "720p", "360p"],
    )
def _mock_probe_side_effect(width: int, height: int):
    """Build a subprocess.run side_effect returning a fixed video probe
    (given width/height) and no audio stream, then a generic success
    result for the main ffmpeg transcode call."""
    def mock_run_side_effect(cmd, **_kwargs):
        if "-select_streams" in cmd and cmd[cmd.index("-select_streams") + 1] == "v:0":
            mock = MagicMock()
            mock.returncode = 0
            mock.stderr = ""
            mock.stdout = json.dumps({
                "streams": [{"r_frame_rate": "30/1", "duration": 6.0, "width": width, "height": height}],
            })
            return mock
        if "-select_streams" in cmd and cmd[cmd.index("-select_streams") + 1] == "a":
            mock = MagicMock()
            mock.returncode = 0
            mock.stderr = ""
            mock.stdout = json.dumps({"streams": []})
            return mock
        mock = MagicMock()
        mock.returncode = 0
        mock.stderr = ""
        return mock
    return mock_run_side_effect


def _get_ffmpeg_cmd(mock_run):
    """Pull the main ffmpeg transcode command (the one with -filter_complex)
    out of a mocked subprocess.run's call list."""
    ffmpeg_calls = [c for c in mock_run.call_args_list
                    if any("filter_complex" in str(a) for a in c[0][0])]
    assert len(ffmpeg_calls) > 0, "no -filter_complex call was made"
    return ffmpeg_calls[0][0][0]

# ─── _run() error handling ────────────────────────────────────────────────────

def test_run_raises_on_nonzero():
    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "ffmpeg error details"
        mock_run.return_value = mock_result

        with pytest.raises(RuntimeError, match="ffmpeg exited 1: ffmpeg error details"):
            FFmpegTranscoder._run(["ffmpeg", "-i", "test.mp4"], label="ffmpeg")


def test_run_uses_errors_replace():
    """Verify that text=True + errors='replace' is passed to subprocess.run."""
    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        FFmpegTranscoder._run(["ffmpeg", "-i", "test.mp4"], timeout=60, label="ffmpeg")

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["text"] is True
        assert call_kwargs["errors"] == "replace"
        assert call_kwargs["timeout"] == 60


# ─── has_audio=True command construction ───────────────────────────────────────

def test_transcode_with_audio_includes_audio_map():
    """When ffprobe detects audio streams, ffmpeg cmd must include -map a:0."""
    def mock_run_side_effect(cmd, **_kwargs):
        # First call: video probe → return metadata
        if "-select_streams" in cmd and cmd[cmd.index("-select_streams") + 1] == "v:0":
            mock = MagicMock()
            mock.returncode = 0
            mock.stderr = ""
            mock.stdout = json.dumps({
                "streams": [{"r_frame_rate": "30/1", "duration": 10.0, "width": 1920, "height": 1080}],
            })
            return mock
        # Second call: audio probe → return audio stream
        if "-select_streams" in cmd and cmd[cmd.index("-select_streams") + 1] == "a":
            mock = MagicMock()
            mock.returncode = 0
            mock.stderr = ""
            mock.stdout = json.dumps({
                "streams": [{"codec_type": "audio"}],
            })
            return mock
        # Third call: main ffmpeg transcode
        mock = MagicMock()
        mock.returncode = 0
        mock.stderr = ""
        return mock

    with patch("subprocess.run", side_effect=mock_run_side_effect) as mock_run:
        s3_mock = MagicMock()
        s3_mock.generate_presigned_url.return_value = "https://s3.example.com/uploads/video.mp4"
        s3_mock.upload_file = MagicMock()

        # Mock thumbnail generation
        with patch("builtins.open", MagicMock()), \
             patch("pathlib.Path.glob", return_value=[]), \
             patch("pathlib.Path.rglob", return_value=[]), \
             patch("pathlib.Path.mkdir"), \
             patch("shutil.rmtree"):
                transcoder = FFmpegTranscoder(s3_mock, "test-bucket")
                job = _make_job(["720p"])
                asyncio.run(transcoder.transcode(job))

        # Find the main ffmpeg command call (the one with -filter_complex)
        ffmpeg_calls = [c for c in mock_run.call_args_list
                        if any("filter_complex" in str(a) for a in c[0][0])]
        assert len(ffmpeg_calls) > 0
        ffmpeg_cmd = ffmpeg_calls[0][0][0]

        # Assert audio map is present
        assert "-map" in ffmpeg_cmd
        # Find all -map args
        maps = [ffmpeg_cmd[i+1] for i, arg in enumerate(ffmpeg_cmd) if arg == "-map"]
        assert "a:0" in maps, f"Expected -map a:0 in ffmpeg cmd, got maps: {maps}"

        # Assert var_stream_map includes audio tracks
        var_stream_idx = ffmpeg_cmd.index("-var_stream_map")
        stream_map = ffmpeg_cmd[var_stream_idx + 1]
        assert "a:0" in stream_map, f"Expected audio track in var_stream_map, got: {stream_map}"


# ─── has_audio=False command construction ─────────────────────────────────────

def test_transcode_without_audio_excludes_audio_map():
    """When ffprobe detects no audio streams, ffmpeg cmd must NOT include -map a:0."""
    def mock_run_side_effect(cmd, **_kwargs):
        # First call: video probe
        if "-select_streams" in cmd and cmd[cmd.index("-select_streams") + 1] == "v:0":
            mock = MagicMock()
            mock.returncode = 0
            mock.stderr = ""
            mock.stdout = json.dumps({
                "streams": [{"r_frame_rate": "30/1", "duration": 10.0, "width": 1920, "height": 1080}],
            })
            return mock
        # Second call: audio probe → NO audio streams
        if "-select_streams" in cmd and cmd[cmd.index("-select_streams") + 1] == "a":
            mock = MagicMock()
            mock.returncode = 0
            mock.stderr = ""
            mock.stdout = json.dumps({"streams": []})
            return mock
        # Third call: main ffmpeg transcode
        mock = MagicMock()
        mock.returncode = 0
        mock.stderr = ""
        return mock

    with patch("subprocess.run", side_effect=mock_run_side_effect) as mock_run:
        s3_mock = MagicMock()
        s3_mock.generate_presigned_url.return_value = "https://s3.example.com/uploads/video.mp4"
        s3_mock.upload_file = MagicMock()

        with patch("builtins.open", MagicMock()), \
             patch("pathlib.Path.glob", return_value=[]), \
             patch("pathlib.Path.rglob", return_value=[]), \
             patch("pathlib.Path.mkdir"), \
             patch("shutil.rmtree"):
                transcoder = FFmpegTranscoder(s3_mock, "test-bucket")
                job = _make_job(["720p"])
                asyncio.run(transcoder.transcode(job))

        # Find the main ffmpeg command call
        ffmpeg_calls = [c for c in mock_run.call_args_list
                        if any("filter_complex" in str(a) for a in c[0][0])]
        assert len(ffmpeg_calls) > 0
        ffmpeg_cmd = ffmpeg_calls[0][0][0]

        # Assert audio map is NOT present
        maps = [ffmpeg_cmd[i+1] for i, arg in enumerate(ffmpeg_cmd) if arg == "-map"]
        assert "a:0" not in maps, f"Expected no -map a:0 in no-audio transcode, got maps: {maps}"

        # Assert var_stream_map is video-only
        var_stream_idx = ffmpeg_cmd.index("-var_stream_map")
        stream_map = ffmpeg_cmd[var_stream_idx + 1]
        assert ",a:" not in stream_map, f"Expected no audio tracks in var_stream_map, got: {stream_map}"


def test_source_smaller_than_ladder_drops_upscaled_renditions():
    """640x360 source requesting the full ladder must produce only the
    360p rendition — mirrors the exact v1.7.0 smoke-test repro."""
    with patch("subprocess.run", side_effect=_mock_probe_side_effect(640, 360)) as mock_run:
        s3_mock = MagicMock()
        s3_mock.generate_presigned_url.return_value = "https://s3.example.com/uploads/video.mp4"
        s3_mock.upload_file = MagicMock()

        with patch("builtins.open", MagicMock()), \
             patch("pathlib.Path.glob", return_value=[]), \
             patch("pathlib.Path.rglob", return_value=[]), \
             patch("pathlib.Path.mkdir"), \
             patch("shutil.rmtree"):
                transcoder = FFmpegTranscoder(s3_mock, "test-bucket")
                job = _make_job(["1080p", "720p", "360p"])
                result = asyncio.run(transcoder.transcode(job))

        assert result.success is True
        ffmpeg_cmd = _get_ffmpeg_cmd(mock_run)

        filter_complex = ffmpeg_cmd[ffmpeg_cmd.index("-filter_complex") + 1]
        assert "1920:1080" not in filter_complex, "1080p rendition should have been dropped"
        assert "1280:720" not in filter_complex, "720p rendition should have been dropped"
        assert "640:360" in filter_complex, "360p rendition should still be present"

        # split=1 → exactly one rendition survived
        assert "split=1" in filter_complex

        var_stream_idx = ffmpeg_cmd.index("-var_stream_map")
        stream_map = ffmpeg_cmd[var_stream_idx + 1]
        assert stream_map.strip() == "v:0", f"expected a single video-only stream, got: {stream_map}"


def test_source_smaller_than_all_requested_keeps_smallest():
    """A source below every requested quality must still yield exactly one
    rendition (the smallest requested), never zero."""
    with patch("subprocess.run", side_effect=_mock_probe_side_effect(426, 240)) as mock_run:
        s3_mock = MagicMock()
        s3_mock.generate_presigned_url.return_value = "https://s3.example.com/uploads/video.mp4"
        s3_mock.upload_file = MagicMock()

        with patch("builtins.open", MagicMock()), \
             patch("pathlib.Path.glob", return_value=[]), \
             patch("pathlib.Path.rglob", return_value=[]), \
             patch("pathlib.Path.mkdir"), \
             patch("shutil.rmtree"):
                transcoder = FFmpegTranscoder(s3_mock, "test-bucket")
                job = _make_job(["1080p", "720p"])  # note: no 360p requested
                result = asyncio.run(transcoder.transcode(job))

        assert result.success is True
        ffmpeg_cmd = _get_ffmpeg_cmd(mock_run)
        filter_complex = ffmpeg_cmd[ffmpeg_cmd.index("-filter_complex") + 1]

        assert "1920:1080" not in filter_complex
        assert "1280:720" in filter_complex, "smallest requested quality (720p) must survive as fallback"
        assert "split=1" in filter_complex


def test_source_larger_than_ladder_keeps_full_ladder():
    """Regression check: a source at/above the top rendition must still
    produce the full requested ladder, unchanged from before the fix."""
    with patch("subprocess.run", side_effect=_mock_probe_side_effect(1920, 1080)) as mock_run:
        s3_mock = MagicMock()
        s3_mock.generate_presigned_url.return_value = "https://s3.example.com/uploads/video.mp4"
        s3_mock.upload_file = MagicMock()

        with patch("builtins.open", MagicMock()), \
             patch("pathlib.Path.glob", return_value=[]), \
             patch("pathlib.Path.rglob", return_value=[]), \
             patch("pathlib.Path.mkdir"), \
             patch("shutil.rmtree"):
                transcoder = FFmpegTranscoder(s3_mock, "test-bucket")
                job = _make_job(["1080p", "720p", "360p"])
                result = asyncio.run(transcoder.transcode(job))

        assert result.success is True
        ffmpeg_cmd = _get_ffmpeg_cmd(mock_run)
        filter_complex = ffmpeg_cmd[ffmpeg_cmd.index("-filter_complex") + 1]

        assert "1920:1080" in filter_complex
        assert "1280:720" in filter_complex
        assert "640:360" in filter_complex
        assert "split=3" in filter_complex


# ─── _run() returns stdout on success ──────────────────────────────────────────

def test_run_returns_stdout():
    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_result.stdout = "output data"
        mock_run.return_value = mock_result

        result = FFmpegTranscoder._run(["echo", "hello"], label="test")
        assert result == "output data"


def test_transcode_returns_probe_metadata():
    t = FFmpegTranscoder(MagicMock(), "bucket")
    video_probe = json.dumps({
        "streams": [{"r_frame_rate": "25/1", "width": 1920, "height": 1080, "duration": "8.0"}],
        "format": {"duration": "8.0"},
    })
    audio_probe = json.dumps({"streams": []})

    def fake_run(cmd, timeout=None, label="ffmpeg"):
        if label == "ffprobe":
            return video_probe if "v:0" in cmd else audio_probe
        return ""

    with patch.object(FFmpegTranscoder, "_run", side_effect=fake_run), \
         patch.object(FFmpegTranscoder, "_get_presigned_url", return_value="http://in"):
        result = asyncio.run(t.transcode(_make_job()))

    assert result.success is True
    assert result.fps == 25.0
    assert result.width == 1920
    assert result.duration_seconds == 8.0


# ─── thread budget ────────────────────────────────────────────────────────────

def _transcode_and_get_cmd(qualities, width=1920, height=1080):
    """Run a transcode against mocked subprocess/filesystem and return the
    ffmpeg command that was built."""
    with patch("subprocess.run", side_effect=_mock_probe_side_effect(width, height)) as mock_run:
        s3_mock = MagicMock()
        s3_mock.generate_presigned_url.return_value = "https://s3.example.com/uploads/video.mp4"
        s3_mock.upload_file = MagicMock()

        with patch("builtins.open", MagicMock()), \
             patch("pathlib.Path.glob", return_value=[]), \
             patch("pathlib.Path.rglob", return_value=[]), \
             patch("pathlib.Path.mkdir"), \
             patch("shutil.rmtree"):
            transcoder = FFmpegTranscoder(s3_mock, "test-bucket")
            result = asyncio.run(transcoder.transcode(_make_job(qualities)))

        assert result.success is True
        return _get_ffmpeg_cmd(mock_run)


def test_every_video_encoder_gets_a_thread_cap():
    """Each rendition's encoder must carry an explicit -threads:v:<i>. Without
    it x264 sizes a frame-thread pool to the whole machine per rendition, which
    is what drove the 5-min load average to 7.68 on 2026-08-16."""
    from packages.transcoder.ffmpeg_transcoder import FFMPEG_THREADS

    cmd = _transcode_and_get_cmd(["1080p", "720p", "360p"])

    encoders = [a for a in cmd if a.startswith("-c:v:")]
    assert len(encoders) == 3, f"expected 3 renditions, got {encoders}"

    for i in range(len(encoders)):
        flag = f"-threads:v:{i}"
        assert flag in cmd, f"{flag} missing; encoder {i} would size its pool to the host"
        assert cmd[cmd.index(flag) + 1] == str(FFMPEG_THREADS)


def test_decoder_and_filter_graph_are_capped():
    """The input decoder and the filter graph build their own pools, so
    capping only the encoders would still leave two unbounded pools."""
    from packages.transcoder.ffmpeg_transcoder import FFMPEG_THREADS

    cmd = _transcode_and_get_cmd(["1080p", "720p", "360p"])

    # -threads before -i applies to the input decoder.
    dec = cmd.index("-threads")
    assert dec < cmd.index("-i"), "-threads must precede -i to bind to the decoder"
    assert cmd[dec + 1] == str(FFMPEG_THREADS)

    assert "-filter_complex_threads" in cmd
    assert cmd[cmd.index("-filter_complex_threads") + 1] == str(FFMPEG_THREADS)


def test_thread_cap_holds_when_ladder_is_trimmed():
    """A source smaller than the ladder drops renditions; the surviving one
    must still be capped (the loop index must not drift off the encoder list)."""
    from packages.transcoder.ffmpeg_transcoder import FFMPEG_THREADS

    cmd = _transcode_and_get_cmd(["1080p", "720p", "360p"], width=640, height=360)

    encoders = [a for a in cmd if a.startswith("-c:v:")]
    assert encoders == ["-c:v:0"], f"expected only the 360p rendition, got {encoders}"
    assert cmd[cmd.index("-threads:v:0") + 1] == str(FFMPEG_THREADS)
    assert "-threads:v:1" not in cmd


def test_thread_cap_is_at_least_one():
    """FFMPEG_THREADS=0 would hand ffmpeg 'auto' and silently restore the
    unbounded pool, so the floor is clamped rather than passed through."""
    import importlib
    import packages.transcoder.ffmpeg_transcoder as mod

    with patch.dict("os.environ", {"FFMPEG_THREADS": "0"}):
        reloaded = importlib.reload(mod)
        assert reloaded.FFMPEG_THREADS == 1
    importlib.reload(mod)
