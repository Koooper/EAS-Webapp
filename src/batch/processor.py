"""
Batch job processor with queue management.
"""

import uuid
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime
import threading

from ..same import SAMEEncoder, SAMEMessage
from .formats import BatchAlert


class JobStatus(Enum):
    """Batch job status."""
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


@dataclass
class BatchJob:
    """Represents a batch processing job."""
    job_id: str
    alerts: List[BatchAlert]
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: int = 0  # 0-100
    current_index: int = 0
    total_count: int = 0
    results: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            'job_id': self.job_id,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'progress': self.progress,
            'current_index': self.current_index,
            'total_count': self.total_count,
            'results_count': len(self.results),
            'errors_count': len(self.errors),
            'errors': self.errors if self.status == JobStatus.FAILED else []
        }


class BatchProcessor:
    """
    Manages batch alert generation with queue.

    Thread-safe batch processing with status tracking.
    """

    def __init__(self):
        self.jobs: Dict[str, BatchJob] = {}
        self._lock = threading.Lock()
        self._processing_thread: Optional[threading.Thread] = None

    def create_job(self, alerts: List[BatchAlert]) -> str:
        """Create a new batch job and return job ID."""
        job_id = str(uuid.uuid4())

        job = BatchJob(
            job_id=job_id,
            alerts=alerts,
            total_count=len(alerts)
        )

        with self._lock:
            self.jobs[job_id] = job

        return job_id

    def get_job(self, job_id: str) -> Optional[BatchJob]:
        """Get job status and results."""
        with self._lock:
            return self.jobs.get(job_id)

    def get_all_jobs(self) -> List[BatchJob]:
        """Get all jobs."""
        with self._lock:
            return list(self.jobs.values())

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending or processing job."""
        with self._lock:
            job = self.jobs.get(job_id)
            if job and job.status in (JobStatus.PENDING, JobStatus.PROCESSING):
                job.status = JobStatus.CANCELLED
                job.completed_at = datetime.now()
                return True
            return False

    def delete_job(self, job_id: str) -> bool:
        """Delete a completed/failed/cancelled job."""
        with self._lock:
            job = self.jobs.get(job_id)
            if job and job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                del self.jobs[job_id]
                return True
            return False

    def start_job(self, job_id: str, generate_audio: bool = True) -> bool:
        """Start processing a job in background thread."""
        with self._lock:
            job = self.jobs.get(job_id)
            if not job or job.status != JobStatus.PENDING:
                return False

            job.status = JobStatus.PROCESSING
            job.started_at = datetime.now()

        # process in background thread
        thread = threading.Thread(
            target=self._process_job,
            args=(job_id, generate_audio),
            daemon=True
        )
        thread.start()
        return True

    def _process_job(self, job_id: str, generate_audio: bool):
        """Process job (runs in background thread)."""
        job = self.get_job(job_id)
        if not job:
            return

        encoder = SAMEEncoder()

        for i, alert in enumerate(job.alerts):
            # check for cancellation
            if job.status == JobStatus.CANCELLED:
                break

            job.current_index = i
            job.progress = int((i / job.total_count) * 100)

            try:
                # create SAME message
                msg = SAMEMessage.create(
                    originator=alert.originator,
                    event=alert.event,
                    locations=alert.locations,
                    duration_minutes=alert.duration_minutes,
                    callsign=alert.callsign
                )

                result = {
                    'index': i,
                    'header': msg.to_string(),
                    'originator': alert.originator,
                    'event': alert.event,
                    'locations': alert.locations,
                    'callsign': alert.callsign
                }

                # optionally generate audio
                if generate_audio:
                    audio = encoder.encode_full_alert(
                        header=msg.to_string(),
                        attention_duration=alert.attention_duration
                    )
                    wav_bytes = encoder.to_bytes(audio)
                    # store size instead of actual audio to save memory
                    result['audio_size'] = len(wav_bytes)
                    result['has_audio'] = True
                else:
                    result['has_audio'] = False

                job.results.append(result)

            except Exception as e:
                error_msg = f"Alert {i}: {str(e)}"
                job.errors.append(error_msg)

        # finalize job
        with self._lock:
            if job.status == JobStatus.CANCELLED:
                pass  # already marked as cancelled
            elif len(job.errors) > 0 and len(job.results) == 0:
                job.status = JobStatus.FAILED
            else:
                job.status = JobStatus.COMPLETED

            job.completed_at = datetime.now()
            job.progress = 100

    def get_job_results(self, job_id: str, start: int = 0, limit: int = 100) -> Optional[List[Dict[str, Any]]]:
        """Get paginated results for a job."""
        job = self.get_job(job_id)
        if not job:
            return None

        return job.results[start:start + limit]

    def cleanup_old_jobs(self, max_age_seconds: int = 3600):
        """Remove completed/failed jobs older than max_age_seconds."""
        now = datetime.now()
        to_delete = []

        with self._lock:
            for job_id, job in self.jobs.items():
                if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                    if job.completed_at:
                        age = (now - job.completed_at).total_seconds()
                        if age > max_age_seconds:
                            to_delete.append(job_id)

            for job_id in to_delete:
                del self.jobs[job_id]

        return len(to_delete)
