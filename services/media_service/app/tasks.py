import logging
import os
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
 
logger = logging.getLogger(__name__)
 
 
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def assemble_recording_chunks(self, recording_id: str):
    """
    Concatenate all RecordingChunk files for a Recording into one file,
    upload to cloud storage, and update the Recording record.
 
    This runs in a Celery worker so the recording pipeline is async and
    never blocks the WebSocket signaling path.
    """
    from .models import Recording, RecordingChunk
 
    try:
        recording = Recording.objects.get(id=recording_id)
        chunks = RecordingChunk.objects.filter(
            recording=recording
        ).order_by("chunk_index")
 
        if not chunks.exists():
            logger.warning("No chunks found for recording %s", recording_id)
            recording.status = "failed"
            recording.save(update_fields=["status"])
            return
 
        # Assemble chunks into one binary buffer
        # In production: stream directly to S3 using multipart upload
        from django.conf import settings
        output_dir = os.path.join(settings.MEDIA_ROOT, "recordings")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{recording_id}.webm")
 
        with open(output_path, "wb") as outfile:
            for chunk in chunks:
                # chunk.file_url is a local path in dev; replace with S3 fetch in prod
                local_path = os.path.join(
                    settings.MEDIA_ROOT,
                    chunk.file_url.lstrip("/media/")
                )
                if os.path.exists(local_path):
                    with open(local_path, "rb") as f:
                        outfile.write(f.read())
 
        file_size = os.path.getsize(output_path)
 
        # TODO: Upload output_path to S3/Cloudinary and get a public URL
        # For now use a local media URL
        file_url = f"/media/recordings/{recording_id}.webm"
 
        recording.file_url = file_url
        recording.file_size = file_size
        recording.status = "ready"
        recording.save(update_fields=["file_url", "file_size", "status"])
 
        logger.info(
            "Recording %s assembled successfully (%d bytes)", recording_id, file_size
        )
 
    except Recording.DoesNotExist:
        logger.error("Recording %s not found", recording_id)
    except Exception as exc:
        logger.exception("Failed to assemble recording %s", recording_id)
        try:
            Recording.objects.filter(id=recording_id).update(status="failed")
        except Exception:
            pass
        raise self.retry(exc=exc)
 
 
@shared_task
def cleanup_inactive_rooms():
    """
    Mark rooms as inactive if all participants have left and the room has
    been idle for more than 30 minutes.
    """
    from .models import Room, Participant
 
    cutoff = timezone.now() - timedelta(minutes=30)
 
    active_rooms = Room.objects.filter(is_active=True)
    ended = 0
    for room in active_rooms:
        has_active = Participant.objects.filter(
            room=room, left_at__isnull=True
        ).exists()
        if not has_active and room.created_at < cutoff:
            room.is_active = False
            room.ended_at = timezone.now()
            room.save(update_fields=["is_active", "ended_at"])
            ended += 1
 
    logger.info("Cleaned up %d inactive rooms", ended)
 
 
@shared_task
def cleanup_old_signals(days: int = 7):
    """Delete delivered signal records older than `days` days."""
    from .models import Signal
 
    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = Signal.objects.filter(
        is_delivered=True, created_at__lt=cutoff
    ).delete()
    logger.info("Deleted %d old signal records", deleted)