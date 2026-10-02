"""#124: _process_video and _process_audio persist probe metadata onto MediaFile."""
from unittest.mock import AsyncMock, MagicMock, patch

from packages.transcoder.base import TranscodeResult


def test_process_video_persists_metadata():
    from apps.api.tasks.transcode_tasks import _process_video

    media_file = MagicMock(duration_seconds=None, width=None, height=None, fps=None,
                           s3_key_raw="raw/x.mp4")
    result = TranscodeResult(
        success=True, hls_prefix="processed/p/a/v", thumbnail_keys=["t.jpg"],
        duration_seconds=71.5, width=3840, height=2160, fps=59.94,
    )
    with patch("packages.transcoder.ffmpeg_transcoder.FFmpegTranscoder") as MockT:
        MockT.return_value.transcode = AsyncMock(return_value=result)
        _process_video(MagicMock(), MagicMock(), MagicMock(), media_file, MagicMock(), "processed/p/a/v")

    assert media_file.duration_seconds == 71.5
    assert media_file.width == 3840
    assert media_file.height == 2160
    assert media_file.fps == 59.94


def test_process_video_leaves_fields_untouched_when_metadata_missing():
    from apps.api.tasks.transcode_tasks import _process_video

    media_file = MagicMock(duration_seconds=None, width=None, height=None, fps=None)
    result = TranscodeResult(success=True, hls_prefix="p", thumbnail_keys=[])
    with patch("packages.transcoder.ffmpeg_transcoder.FFmpegTranscoder") as MockT:
        MockT.return_value.transcode = AsyncMock(return_value=result)
        _process_video(MagicMock(), MagicMock(), MagicMock(), media_file, MagicMock(), "p")

    assert media_file.duration_seconds is None
    assert media_file.fps is None


def test_process_audio_persists_duration():
    from apps.api.tasks.transcode_tasks import _process_audio

    media_file = MagicMock(duration_seconds=None)
    with patch("packages.transcoder.image_processor.process_audio",
               return_value={"mp3_key": "k.mp3", "waveform_key": "w.json", "duration_seconds": 12.5}):
        _process_audio(MagicMock(), MagicMock(), MagicMock(), media_file, MagicMock(), "prefix")

    assert media_file.duration_seconds == 12.5
    assert media_file.s3_key_processed == "k.mp3"


def test_process_asset_is_confirmed_late_and_workers_do_not_hoard_jobs():
    """A worker killed mid-encode must not silently lose the job (acks_late), and with late acks a
    worker reserving several jobs per slot would let a long queue time out its own reservations
    and run the same file twice - so one job at a time and a visibility timeout above any encode."""
    from apps.api.tasks.celery_app import celery_app
    from apps.api.tasks.transcode_tasks import process_asset
    from packages.transcoder.ffmpeg_transcoder import encode_timeout_seconds

    assert process_asset.acks_late is True
    assert process_asset.reject_on_worker_lost is not True   # would loop on a file that kills its worker
    assert celery_app.conf.worker_prefetch_multiplier == 1
    # A job unconfirmed for longer than this is handed to a second worker, so no encode of a video
    # up to 30 minutes long may be allowed to outlive its own reservation.
    visibility = celery_app.conf.broker_transport_options["visibility_timeout"]
    assert encode_timeout_seconds(30 * 60) <= visibility
