"""
Beeper Integration

Operational integration with Beeper notification service for
benchmark alerts, deployment notifications, and quality warnings.
"""

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx
import structlog

from hermes.config import get_settings

settings = get_settings()
logger = structlog.get_logger()


class NotificationChannel(str, Enum):
    """Notification delivery channels."""
    
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    IN_APP = "in_app"
    MS_TEAMS = "teams"


class NotificationPriority(str, Enum):
    """Notification priority levels."""
    
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationType(str, Enum):
    """Types of Hermes notifications."""
    
    BENCHMARK_COMPLETE = "benchmark_complete"
    BENCHMARK_REGRESSION = "benchmark_regression"
    GATE_FAILED = "gate_failed"
    GATE_PASSED = "gate_passed"
    DEPLOYMENT_STARTED = "deployment_started"
    DEPLOYMENT_COMPLETE = "deployment_complete"
    DEPLOYMENT_FAILED = "deployment_failed"
    SYNC_COMPLETE = "sync_complete"
    SYNC_CONFLICT = "sync_conflict"
    SUGGESTION_READY = "suggestion_ready"


@dataclass
class Notification:
    """A notification to send via Beeper."""
    
    id: uuid.UUID
    title: str
    body: str
    notification_type: NotificationType
    priority: NotificationPriority
    channels: List[NotificationChannel]
    recipients: List[str]  # User IDs or email addresses
    data: Optional[Dict[str, Any]] = None
    link: Optional[str] = None
    actions: Optional[List[Dict[str, str]]] = None  # {label, url}


class BeeperClient:
    """
    Operational client for Beeper notification service.
    
    Provides notifications for:
    - Benchmark results and regressions
    - Quality gate status
    - Deployment events
    - Sync status and conflicts
    - Improvement suggestions
    """

    def __init__(
        self,
        base_url: str = None,
        api_key: str = None,
        enabled: bool = None,
    ):
        self.base_url = base_url or settings.beeper_url
        self.api_key = api_key or settings.beeper_api_key
        self.enabled = enabled if enabled is not None else settings.beeper_enabled
        self._http_client: Optional[httpx.AsyncClient] = None
        
        logger.info(
            "Beeper client initialized",
            enabled=self.enabled,
            url=self.base_url,
        )

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._http_client

    async def send_notification(self, notification: Notification) -> bool:
        """Send a notification via Beeper."""
        if not self.enabled:
            logger.debug(
                "Notification skipped (Beeper disabled)",
                type=notification.notification_type.value,
                title=notification.title,
            )
            return True

        try:
            client = await self._get_http_client()
            response = await client.post(
                f"{self.base_url}/api/v1/notifications",
                json={
                    "id": str(notification.id),
                    "title": notification.title,
                    "body": notification.body,
                    "type": notification.notification_type.value,
                    "priority": notification.priority.value,
                    "channels": [c.value for c in notification.channels],
                    "recipients": notification.recipients,
                    "data": notification.data,
                    "link": notification.link,
                    "actions": notification.actions,
                    "source": "hermes",
                    "source_version": settings.app_version,
                },
            )
            
            success = response.status_code in (200, 201, 202)
            
            if success:
                logger.debug(
                    "Notification sent",
                    type=notification.notification_type.value,
                    recipients=len(notification.recipients),
                )
            else:
                logger.warning(
                    "Notification failed",
                    status_code=response.status_code,
                    type=notification.notification_type.value,
                )
            
            return success
        except httpx.HTTPError as e:
            logger.warning(
                "Failed to send notification",
                error=str(e),
                type=notification.notification_type.value,
            )
            return False

    # =========================================================================
    # Benchmark Notifications
    # =========================================================================

    async def notify_benchmark_complete(
        self,
        prompt_id: uuid.UUID,
        prompt_name: str,
        score: float,
        delta: Optional[float],
        recipients: List[str],
    ) -> bool:
        """Send benchmark completion notification."""
        if delta:
            direction = "improved" if delta > 0 else "decreased"
            delta_str = f"{'+' if delta > 0 else ''}{delta:.1f}%"
            body = f"Score: {score:.1f}% ({direction} by {delta_str})"
        else:
            body = f"Score: {score:.1f}%"

        # Determine priority based on score
        if score >= 90:
            priority = NotificationPriority.LOW
        elif score >= 80:
            priority = NotificationPriority.NORMAL
        else:
            priority = NotificationPriority.HIGH

        notification = Notification(
            id=uuid.uuid4(),
            title=f"✓ Benchmark Complete: {prompt_name}",
            body=body,
            notification_type=NotificationType.BENCHMARK_COMPLETE,
            priority=priority,
            channels=[NotificationChannel.IN_APP, NotificationChannel.SLACK],
            recipients=recipients,
            data={
                "prompt_id": str(prompt_id),
                "score": score,
                "delta": delta,
            },
            link=f"/prompts/{prompt_id}/benchmarks",
            actions=[
                {"label": "View Results", "url": f"/prompts/{prompt_id}/benchmarks"},
                {"label": "Run Again", "url": f"/prompts/{prompt_id}/benchmark/run"},
            ],
        )

        return await self.send_notification(notification)

    async def notify_quality_regression(
        self,
        prompt_id: uuid.UUID,
        prompt_name: str,
        old_score: float,
        new_score: float,
        recipients: List[str],
    ) -> bool:
        """Send quality regression alert."""
        drop = old_score - new_score
        
        notification = Notification(
            id=uuid.uuid4(),
            title=f"⚠️ Quality Regression: {prompt_name}",
            body=f"Score dropped from {old_score:.1f}% to {new_score:.1f}% (-{drop:.1f}%)",
            notification_type=NotificationType.BENCHMARK_REGRESSION,
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
                "drop": drop,
            },
            link=f"/prompts/{prompt_id}/benchmarks",
            actions=[
                {"label": "View History", "url": f"/prompts/{prompt_id}/versions"},
                {"label": "Rollback", "url": f"/prompts/{prompt_id}/rollback"},
            ],
        )

        return await self.send_notification(notification)

    async def notify_gate_failed(
        self,
        prompt_id: uuid.UUID,
        prompt_name: str,
        score: float,
        threshold: float,
        recipients: List[str],
    ) -> bool:
        """Send quality gate failure notification."""
        notification = Notification(
            id=uuid.uuid4(),
            title=f"🚫 Quality Gate Failed: {prompt_name}",
            body=f"Score {score:.1f}% is below threshold {threshold:.1f}%",
            notification_type=NotificationType.GATE_FAILED,
            priority=NotificationPriority.HIGH,
            channels=[NotificationChannel.IN_APP, NotificationChannel.SLACK],
            recipients=recipients,
            data={
                "prompt_id": str(prompt_id),
                "score": score,
                "threshold": threshold,
                "gap": threshold - score,
            },
            link=f"/prompts/{prompt_id}/benchmarks",
            actions=[
                {"label": "View Details", "url": f"/prompts/{prompt_id}/benchmarks"},
                {"label": "Get Suggestions", "url": f"/prompts/{prompt_id}/critique"},
            ],
        )

        return await self.send_notification(notification)

    async def notify_gate_passed(
        self,
        prompt_id: uuid.UUID,
        prompt_name: str,
        score: float,
        threshold: float,
        recipients: List[str],
    ) -> bool:
        """Send quality gate passed notification."""
        notification = Notification(
            id=uuid.uuid4(),
            title=f"✅ Quality Gate Passed: {prompt_name}",
            body=f"Score {score:.1f}% exceeds threshold {threshold:.1f}%",
            notification_type=NotificationType.GATE_PASSED,
            priority=NotificationPriority.NORMAL,
            channels=[NotificationChannel.IN_APP],
            recipients=recipients,
            data={
                "prompt_id": str(prompt_id),
                "score": score,
                "threshold": threshold,
            },
            link=f"/prompts/{prompt_id}",
        )

        return await self.send_notification(notification)

    # =========================================================================
    # Deployment Notifications
    # =========================================================================

    async def notify_deployment(
        self,
        prompt_id: uuid.UUID,
        prompt_name: str,
        version: str,
        environment: str,
        recipients: List[str],
        status: str = "complete",
    ) -> bool:
        """Send deployment notification."""
        if status == "started":
            title = f"🚀 Deployment Started: {prompt_name}"
            body = f"Version {version} deploying to {environment}"
            notification_type = NotificationType.DEPLOYMENT_STARTED
            priority = NotificationPriority.NORMAL
        elif status == "complete":
            title = f"✓ Deployment Complete: {prompt_name}"
            body = f"Version {version} deployed to {environment}"
            notification_type = NotificationType.DEPLOYMENT_COMPLETE
            priority = NotificationPriority.NORMAL
        else:  # failed
            title = f"❌ Deployment Failed: {prompt_name}"
            body = f"Version {version} failed to deploy to {environment}"
            notification_type = NotificationType.DEPLOYMENT_FAILED
            priority = NotificationPriority.URGENT

        notification = Notification(
            id=uuid.uuid4(),
            title=title,
            body=body,
            notification_type=notification_type,
            priority=priority,
            channels=[NotificationChannel.IN_APP, NotificationChannel.SLACK],
            recipients=recipients,
            data={
                "prompt_id": str(prompt_id),
                "version": version,
                "environment": environment,
                "status": status,
            },
            link=f"/prompts/{prompt_id}/deployments",
        )

        return await self.send_notification(notification)

    # =========================================================================
    # Sync Notifications
    # =========================================================================

    async def notify_sync_complete(
        self,
        imported: int,
        updated: int,
        conflicts: int,
        recipients: List[str],
    ) -> bool:
        """Send nursery sync completion notification."""
        notification = Notification(
            id=uuid.uuid4(),
            title="✓ Nursery Sync Complete",
            body=f"Imported: {imported}, Updated: {updated}, Conflicts: {conflicts}",
            notification_type=NotificationType.SYNC_COMPLETE,
            priority=NotificationPriority.NORMAL if conflicts == 0 else NotificationPriority.HIGH,
            channels=[NotificationChannel.IN_APP],
            recipients=recipients,
            data={
                "imported": imported,
                "updated": updated,
                "conflicts": conflicts,
            },
            link="/sync/nursery",
        )

        return await self.send_notification(notification)

    async def notify_sync_conflict(
        self,
        prompt_name: str,
        local_version: str,
        nursery_version: str,
        recipients: List[str],
    ) -> bool:
        """Send sync conflict notification."""
        notification = Notification(
            id=uuid.uuid4(),
            title=f"⚠️ Sync Conflict: {prompt_name}",
            body=f"Local v{local_version} conflicts with Nursery v{nursery_version}",
            notification_type=NotificationType.SYNC_CONFLICT,
            priority=NotificationPriority.HIGH,
            channels=[NotificationChannel.IN_APP, NotificationChannel.SLACK],
            recipients=recipients,
            data={
                "prompt_name": prompt_name,
                "local_version": local_version,
                "nursery_version": nursery_version,
            },
            link="/sync/conflicts",
            actions=[
                {"label": "Resolve", "url": "/sync/conflicts"},
            ],
        )

        return await self.send_notification(notification)

    # =========================================================================
    # Suggestion Notifications
    # =========================================================================

    async def notify_suggestions_ready(
        self,
        prompt_id: uuid.UUID,
        prompt_name: str,
        suggestion_count: int,
        improvement_potential: float,
        recipients: List[str],
    ) -> bool:
        """Send notification when ASRBS suggestions are ready."""
        notification = Notification(
            id=uuid.uuid4(),
            title=f"💡 Improvements Available: {prompt_name}",
            body=f"{suggestion_count} suggestions found (potential +{improvement_potential:.1f}%)",
            notification_type=NotificationType.SUGGESTION_READY,
            priority=NotificationPriority.LOW,
            channels=[NotificationChannel.IN_APP],
            recipients=recipients,
            data={
                "prompt_id": str(prompt_id),
                "suggestion_count": suggestion_count,
                "improvement_potential": improvement_potential,
            },
            link=f"/prompts/{prompt_id}/critique",
            actions=[
                {"label": "Review", "url": f"/prompts/{prompt_id}/critique"},
            ],
        )

        return await self.send_notification(notification)

    async def close(self):
        """Close HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None


# Singleton instance
_beeper_client: Optional[BeeperClient] = None


def get_beeper_client() -> BeeperClient:
    """Get the Beeper client singleton."""
    global _beeper_client
    if _beeper_client is None:
        _beeper_client = BeeperClient()
    return _beeper_client


async def shutdown_beeper_client():
    """Shutdown the Beeper client."""
    global _beeper_client
    if _beeper_client:
        await _beeper_client.close()
        _beeper_client = None
