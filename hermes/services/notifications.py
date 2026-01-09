"""
Beeper Notification Service

Sends alerts and notifications via Beeper.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx

from hermes.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class NotificationType(str, Enum):
    """Types of notifications."""
    
    BENCHMARK_COMPLETE = "benchmark_complete"
    BENCHMARK_REGRESSION = "benchmark_regression"
    BENCHMARK_IMPROVEMENT = "benchmark_improvement"
    PROMPT_DEPLOYED = "prompt_deployed"
    PROMPT_CREATED = "prompt_created"
    SYNC_COMPLETE = "sync_complete"
    SYNC_CONFLICT = "sync_conflict"
    ERROR = "error"


class NotificationPriority(str, Enum):
    """Notification priority levels."""
    
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Notification:
    """A notification to send."""
    
    type: NotificationType
    title: str
    message: str
    priority: NotificationPriority = NotificationPriority.NORMAL
    data: Dict[str, Any] = None
    recipients: List[str] = None
    channels: List[str] = None
    
    def __post_init__(self):
        if self.data is None:
            self.data = {}
        if self.recipients is None:
            self.recipients = []
        if self.channels is None:
            self.channels = ["hermes"]


class BeeperClient:
    """Client for Beeper notification service.
    
    Beeper provides unified notification delivery across
    channels (email, Slack, SMS, push).
    """
    
    def __init__(
        self,
        beeper_url: Optional[str] = None,
        api_key: Optional[str] = None,
        default_channel: str = "hermes",
    ):
        """Initialize Beeper client.
        
        Args:
            beeper_url: Beeper service URL
            api_key: Beeper API key
            default_channel: Default notification channel
        """
        self.beeper_url = beeper_url or settings.beeper_url
        self.api_key = api_key or settings.beeper_api_key
        self.default_channel = default_channel
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            headers = {
                "Content-Type": "application/json",
                "X-API-Key": self.api_key,
            }
            self._client = httpx.AsyncClient(
                base_url=self.beeper_url,
                headers=headers,
                timeout=10.0,
            )
        return self._client
    
    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def send(self, notification: Notification) -> bool:
        """Send a notification via Beeper.
        
        Args:
            notification: Notification to send
            
        Returns:
            True if sent successfully
        """
        if not settings.beeper_enabled:
            logger.debug(f"Beeper disabled, skipping: {notification.title}")
            return True
        
        if not self.api_key:
            logger.warning("Beeper API key not configured")
            return False
        
        client = await self._get_client()
        
        payload = {
            "type": notification.type.value,
            "title": notification.title,
            "message": notification.message,
            "priority": notification.priority.value,
            "data": notification.data,
            "channels": notification.channels or [self.default_channel],
            "recipients": notification.recipients,
            "source": "hermes",
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        try:
            response = await client.post("/api/v1/notifications", json=payload)
            response.raise_for_status()
            logger.info(f"Sent notification: {notification.title}")
            return True
        except httpx.HTTPError as e:
            logger.error(f"Failed to send notification: {e}")
            return False
    
    async def notify_benchmark_complete(
        self,
        prompt_slug: str,
        prompt_name: str,
        score: float,
        previous_score: Optional[float] = None,
        recommendations: Optional[List[str]] = None,
        recipients: Optional[List[str]] = None,
    ) -> bool:
        """Send benchmark completion notification.
        
        Args:
            prompt_slug: Prompt slug
            prompt_name: Prompt display name
            score: New benchmark score
            previous_score: Previous benchmark score
            recommendations: Improvement recommendations
            recipients: Notification recipients
            
        Returns:
            True if sent successfully
        """
        # Determine notification type and priority
        if previous_score is not None:
            delta = score - previous_score
            if delta < -5:
                notif_type = NotificationType.BENCHMARK_REGRESSION
                priority = NotificationPriority.HIGH
                emoji = "🔴"
                status = f"regressed by {abs(delta):.1f}%"
            elif delta > 5:
                notif_type = NotificationType.BENCHMARK_IMPROVEMENT
                priority = NotificationPriority.NORMAL
                emoji = "🟢"
                status = f"improved by {delta:.1f}%"
            else:
                notif_type = NotificationType.BENCHMARK_COMPLETE
                priority = NotificationPriority.LOW
                emoji = "🔵"
                status = f"stable at {score:.1f}%"
        else:
            notif_type = NotificationType.BENCHMARK_COMPLETE
            priority = NotificationPriority.NORMAL
            emoji = "🔵"
            status = f"scored {score:.1f}%"
        
        title = f"{emoji} Benchmark: {prompt_name}"
        message = f"Prompt `{prompt_slug}` {status}"
        
        if recommendations:
            message += f"\n\nRecommendations:\n" + "\n".join(f"• {r}" for r in recommendations[:3])
        
        notification = Notification(
            type=notif_type,
            title=title,
            message=message,
            priority=priority,
            data={
                "prompt_slug": prompt_slug,
                "score": score,
                "previous_score": previous_score,
                "recommendations": recommendations,
            },
            recipients=recipients,
        )
        
        return await self.send(notification)
    
    async def notify_prompt_deployed(
        self,
        prompt_slug: str,
        prompt_name: str,
        version: str,
        deployed_by: str,
        recipients: Optional[List[str]] = None,
    ) -> bool:
        """Send prompt deployment notification.
        
        Args:
            prompt_slug: Prompt slug
            prompt_name: Prompt display name
            version: Deployed version
            deployed_by: User who deployed
            recipients: Notification recipients
            
        Returns:
            True if sent successfully
        """
        notification = Notification(
            type=NotificationType.PROMPT_DEPLOYED,
            title=f"🚀 Deployed: {prompt_name}",
            message=f"Prompt `{prompt_slug}` v{version} deployed to production by {deployed_by}",
            priority=NotificationPriority.NORMAL,
            data={
                "prompt_slug": prompt_slug,
                "version": version,
                "deployed_by": deployed_by,
            },
            recipients=recipients,
        )
        
        return await self.send(notification)
    
    async def notify_sync_complete(
        self,
        imported: int,
        exported: int,
        conflicts: int,
        recipients: Optional[List[str]] = None,
    ) -> bool:
        """Send nursery sync completion notification.
        
        Args:
            imported: Number of prompts imported
            exported: Number of prompts exported
            conflicts: Number of conflicts
            recipients: Notification recipients
            
        Returns:
            True if sent successfully
        """
        if conflicts > 0:
            notif_type = NotificationType.SYNC_CONFLICT
            priority = NotificationPriority.HIGH
            emoji = "⚠️"
        else:
            notif_type = NotificationType.SYNC_COMPLETE
            priority = NotificationPriority.LOW
            emoji = "✅"
        
        notification = Notification(
            type=notif_type,
            title=f"{emoji} Nursery Sync Complete",
            message=f"Imported: {imported}, Exported: {exported}, Conflicts: {conflicts}",
            priority=priority,
            data={
                "imported": imported,
                "exported": exported,
                "conflicts": conflicts,
            },
            recipients=recipients,
        )
        
        return await self.send(notification)
    
    async def notify_error(
        self,
        title: str,
        error_message: str,
        context: Optional[Dict[str, Any]] = None,
        recipients: Optional[List[str]] = None,
    ) -> bool:
        """Send error notification.
        
        Args:
            title: Error title
            error_message: Error details
            context: Additional context
            recipients: Notification recipients
            
        Returns:
            True if sent successfully
        """
        notification = Notification(
            type=NotificationType.ERROR,
            title=f"❌ {title}",
            message=error_message,
            priority=NotificationPriority.URGENT,
            data=context or {},
            recipients=recipients,
        )
        
        return await self.send(notification)


# Global client instance
_beeper_client: Optional[BeeperClient] = None


def get_beeper_client() -> BeeperClient:
    """Get or create Beeper client."""
    global _beeper_client
    if _beeper_client is None:
        _beeper_client = BeeperClient()
    return _beeper_client


async def send_notification(notification: Notification) -> bool:
    """Convenience function to send a notification.
    
    Args:
        notification: Notification to send
        
    Returns:
        True if sent successfully
    """
    client = get_beeper_client()
    return await client.send(notification)
