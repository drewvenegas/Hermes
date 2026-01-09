"""
Beeper Integration

Integration with Beeper notification service.
"""

import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import httpx

from hermes.config import get_settings

settings = get_settings()


class NotificationChannel(str, Enum):
    """Notification delivery channels."""
    
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    IN_APP = "in_app"


class NotificationPriority(str, Enum):
    """Notification priority levels."""
    
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Notification:
    """A notification to send via Beeper."""
    
    id: uuid.UUID
    title: str
    body: str
    priority: NotificationPriority
    channels: list[NotificationChannel]
    recipients: list[str]  # User IDs or email addresses
    data: Optional[dict] = None
    link: Optional[str] = None


class BeeperClient:
    """Client for Beeper notification service."""

    def __init__(self):
        self.base_url = settings.beeper_url
        self.api_key = settings.beeper_api_key
        self.enabled = settings.beeper_enabled
        self._client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

    async def send_notification(self, notification: Notification) -> bool:
        """Send a notification via Beeper."""
        if not self.enabled:
            return True

        try:
            response = await self._client.post(
                f"{self.base_url}/api/v1/notifications",
                json={
                    "id": str(notification.id),
                    "title": notification.title,
                    "body": notification.body,
                    "priority": notification.priority.value,
                    "channels": [c.value for c in notification.channels],
                    "recipients": notification.recipients,
                    "data": notification.data,
                    "link": notification.link,
                    "source": "hermes",
                },
            )
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def notify_benchmark_complete(
        self,
        prompt_id: uuid.UUID,
        prompt_name: str,
        score: float,
        delta: Optional[float],
        recipients: list[str],
    ) -> bool:
        """Send benchmark completion notification."""
        direction = "improved" if delta and delta > 0 else "decreased"
        delta_str = f"{'+' if delta and delta > 0 else ''}{delta:.1f}%" if delta else ""

        notification = Notification(
            id=uuid.uuid4(),
            title=f"Benchmark Complete: {prompt_name}",
            body=f"Score: {score:.1f}%{f' ({direction} by {delta_str})' if delta else ''}",
            priority=NotificationPriority.NORMAL,
            channels=[NotificationChannel.IN_APP, NotificationChannel.SLACK],
            recipients=recipients,
            data={
                "prompt_id": str(prompt_id),
                "score": score,
                "delta": delta,
            },
            link=f"/prompts/{prompt_id}",
        )

        return await self.send_notification(notification)

    async def notify_deployment(
        self,
        prompt_id: uuid.UUID,
        prompt_name: str,
        version: str,
        environment: str,
        recipients: list[str],
    ) -> bool:
        """Send deployment notification."""
        notification = Notification(
            id=uuid.uuid4(),
            title=f"Prompt Deployed: {prompt_name}",
            body=f"Version {version} deployed to {environment}",
            priority=NotificationPriority.HIGH,
            channels=[NotificationChannel.IN_APP, NotificationChannel.SLACK],
            recipients=recipients,
            data={
                "prompt_id": str(prompt_id),
                "version": version,
                "environment": environment,
            },
            link=f"/prompts/{prompt_id}",
        )

        return await self.send_notification(notification)

    async def notify_quality_regression(
        self,
        prompt_id: uuid.UUID,
        prompt_name: str,
        old_score: float,
        new_score: float,
        recipients: list[str],
    ) -> bool:
        """Send quality regression alert."""
        notification = Notification(
            id=uuid.uuid4(),
            title=f"Quality Regression: {prompt_name}",
            body=f"Score dropped from {old_score:.1f}% to {new_score:.1f}%",
            priority=NotificationPriority.URGENT,
            channels=[
                NotificationChannel.IN_APP,
                NotificationChannel.SLACK,
                NotificationChannel.EMAIL,
            ],
            recipients=recipients,
            data={
                "prompt_id": str(prompt_id),
                "old_score": old_score,
                "new_score": new_score,
            },
            link=f"/prompts/{prompt_id}",
        )

        return await self.send_notification(notification)

    async def close(self):
        """Close HTTP client."""
        await self._client.aclose()
