"""GCP Cloud Tasks backend for token refresh scheduling.

Creates one-time HTTP tasks that call POST /api/v1/vault/internal/tokens/refresh-due
at the scheduled time. Cloud Tasks handles retry with exponential backoff.

Environment variables:
- CLOUD_TASKS_PROJECT: GCP project ID
- CLOUD_TASKS_LOCATION: GCP region (e.g., us-central1)
- CLOUD_TASKS_QUEUE: Queue name (default: token-refresh)
- CONTROL_PLANE_URL: Cloud Run service URL for the control plane
- GATEWAY_INTERNAL_API_TOKEN: Internal API token for auth
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2

from app.services.token_refresh_scheduler import TokenRefreshScheduler

logger = logging.getLogger(__name__)


class CloudTasksScheduler(TokenRefreshScheduler):
    """GCP Cloud Tasks-based scheduler for production.

    Each token refresh is a one-time HTTP task scheduled at
    (expires_at - 10 min). Cloud Tasks auto-retries on 5xx.
    Task names are deterministic from token_ref to prevent duplicates.
    """

    def __init__(
        self,
        project: Optional[str] = None,
        location: Optional[str] = None,
        queue: Optional[str] = None,
        control_plane_url: Optional[str] = None,
    ) -> None:
        super().__init__()
        self._project = project or os.environ["CLOUD_TASKS_PROJECT"]
        self._location = location or os.environ["CLOUD_TASKS_LOCATION"]
        self._queue = queue or os.getenv("CLOUD_TASKS_QUEUE", "token-refresh")
        self._control_plane_url = (
            control_plane_url or os.environ["CONTROL_PLANE_URL"]
        ).rstrip("/")
        self._internal_token = os.getenv(
            "GATEWAY_INTERNAL_API_TOKEN", "gateway-internal-secret-token"
        )
        self._client = tasks_v2.CloudTasksClient()
        self._parent = self._client.queue_path(
            self._project, self._location, self._queue
        )

    def _task_name(self, token_ref: str) -> str:
        """Deterministic task name from token_ref."""
        ref_hash = hashlib.sha256(token_ref.encode()).hexdigest()[:16]
        return f"{self._parent}/tasks/refresh-{ref_hash}"

    def schedule_refresh(
        self,
        token_ref: str,
        service_id: str,
        user_id: str,
        refresh_at: datetime,
    ) -> None:
        self.cancel_refresh(token_ref)

        if refresh_at.tzinfo is None:
            refresh_at = refresh_at.replace(tzinfo=timezone.utc)

        schedule_time = timestamp_pb2.Timestamp()
        schedule_time.FromDatetime(refresh_at)

        payload = json.dumps({
            "token_ref": token_ref,
            "service_id": service_id,
            "user_id": user_id,
        })

        task = tasks_v2.Task(
            name=self._task_name(token_ref),
            schedule_time=schedule_time,
            http_request=tasks_v2.HttpRequest(
                http_method=tasks_v2.HttpMethod.POST,
                url=f"{self._control_plane_url}/api/v1/vault/internal/tokens/refresh-due",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._internal_token}",
                },
                body=payload.encode(),
            ),
        )

        try:
            self._client.create_task(
                request=tasks_v2.CreateTaskRequest(
                    parent=self._parent,
                    task=task,
                )
            )
            self.metrics.scheduled_count += 1
            logger.info(
                "Cloud Tasks: scheduled refresh for service=%s user=%s at %s",
                service_id,
                user_id,
                refresh_at.isoformat(),
            )
        except Exception as e:
            logger.error(
                "Cloud Tasks: failed to schedule refresh for service=%s user=%s: %s",
                service_id,
                user_id,
                e,
            )

    def cancel_refresh(self, token_ref: str) -> None:
        task_name = self._task_name(token_ref)
        try:
            self._client.delete_task(
                request=tasks_v2.DeleteTaskRequest(name=task_name)
            )
            self.metrics.cancel_count += 1
            logger.debug("Cloud Tasks: cancelled task %s", task_name)
        except Exception:
            pass

    def shutdown(self) -> None:
        logger.info("CloudTasksScheduler shutdown (tasks persist in queue)")

    @property
    def pending_count(self) -> int:
        return self.metrics.scheduled_count - self.metrics.success_count - self.metrics.failure_count - self.metrics.cancel_count
