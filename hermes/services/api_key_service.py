"""
API Key Service

Manages API keys for programmatic access to Hermes.
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Optional

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from hermes.models.api_key import APIKey, STANDARD_SCOPES

logger = structlog.get_logger()


class APIKeyService:
    """
    Service for managing API keys.
    
    Provides functionality for creating, validating, and revoking API keys
    for programmatic access to the Hermes API.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_key(
        self,
        name: str,
        created_by: uuid.UUID,
        scopes: Optional[List[str]] = None,
        description: Optional[str] = None,
        expires_in_days: Optional[int] = None,
        organization_id: Optional[uuid.UUID] = None,
        allowed_ips: Optional[List[str]] = None,
        metadata: Optional[dict] = None,
    ) -> tuple[APIKey, str]:
        """
        Create a new API key.
        
        Returns:
            Tuple of (APIKey model, raw key string)
            
        Note:
            The raw key string is only returned once at creation time.
            It cannot be retrieved later - only the hash is stored.
        """
        # Validate scopes
        scopes = scopes or ["prompts:read"]
        invalid_scopes = set(scopes) - set(STANDARD_SCOPES)
        if invalid_scopes:
            raise ValueError(f"Invalid scopes: {invalid_scopes}")
        
        # Generate the key
        raw_key, key_prefix, key_hash = APIKey.generate_key()
        
        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        # Create the API key record
        api_key = APIKey(
            id=uuid.uuid4(),
            name=name,
            description=description,
            key_prefix=key_prefix,
            key_hash=key_hash,
            scopes=scopes,
            expires_at=expires_at,
            created_by=created_by,
            organization_id=organization_id,
            allowed_ips=allowed_ips,
            metadata=metadata or {},
        )
        
        self.db.add(api_key)
        
        logger.info(
            "API key created",
            key_id=str(api_key.id),
            name=name,
            prefix=key_prefix,
            scopes=scopes,
            created_by=str(created_by),
        )
        
        return api_key, raw_key
    
    async def validate_key(
        self,
        raw_key: str,
        required_scope: Optional[str] = None,
        client_ip: Optional[str] = None,
    ) -> Optional[APIKey]:
        """
        Validate an API key and optionally check scope.
        
        Returns:
            The APIKey if valid, None otherwise
        """
        # Hash the provided key
        key_hash = APIKey.hash_key(raw_key)
        
        # Look up by hash
        result = await self.db.execute(
            select(APIKey).where(APIKey.key_hash == key_hash)
        )
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            logger.warning("API key not found", key_prefix=raw_key[:12] if len(raw_key) >= 12 else "invalid")
            return None
        
        # Check if key is valid
        if not api_key.is_valid():
            logger.warning(
                "API key invalid",
                key_id=str(api_key.id),
                is_active=api_key.is_active,
                expired=api_key.expires_at and datetime.utcnow() > api_key.expires_at,
                revoked=api_key.revoked_at is not None,
            )
            return None
        
        # Check IP allowlist
        if api_key.allowed_ips and client_ip:
            if client_ip not in api_key.allowed_ips:
                logger.warning(
                    "API key IP not allowed",
                    key_id=str(api_key.id),
                    client_ip=client_ip,
                )
                return None
        
        # Check scope
        if required_scope and not api_key.has_scope(required_scope):
            logger.warning(
                "API key missing required scope",
                key_id=str(api_key.id),
                required_scope=required_scope,
                key_scopes=api_key.scopes,
            )
            return None
        
        # Update last used
        await self.db.execute(
            update(APIKey)
            .where(APIKey.id == api_key.id)
            .values(
                last_used_at=datetime.utcnow(),
                use_count=APIKey.use_count + 1,
            )
        )
        
        return api_key
    
    async def get_key(self, key_id: uuid.UUID) -> Optional[APIKey]:
        """Get an API key by ID."""
        result = await self.db.execute(
            select(APIKey).where(APIKey.id == key_id)
        )
        return result.scalar_one_or_none()
    
    async def get_key_by_prefix(self, key_prefix: str) -> Optional[APIKey]:
        """Get an API key by its prefix."""
        result = await self.db.execute(
            select(APIKey).where(APIKey.key_prefix == key_prefix)
        )
        return result.scalar_one_or_none()
    
    async def list_keys(
        self,
        created_by: Optional[uuid.UUID] = None,
        organization_id: Optional[uuid.UUID] = None,
        include_revoked: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[APIKey], int]:
        """
        List API keys with optional filtering.
        
        Returns:
            Tuple of (list of APIKey, total count)
        """
        query = select(APIKey)
        
        if created_by:
            query = query.where(APIKey.created_by == created_by)
        if organization_id:
            query = query.where(APIKey.organization_id == organization_id)
        if not include_revoked:
            query = query.where(APIKey.revoked_at.is_(None))
        
        # Get total count
        from sqlalchemy import func
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Apply pagination
        query = query.order_by(APIKey.created_at.desc())
        query = query.offset(offset).limit(limit)
        
        result = await self.db.execute(query)
        keys = result.scalars().all()
        
        return list(keys), total
    
    async def revoke_key(
        self,
        key_id: uuid.UUID,
        revoked_by: uuid.UUID,
        reason: Optional[str] = None,
    ) -> bool:
        """
        Revoke an API key.
        
        Returns:
            True if revoked, False if key not found
        """
        api_key = await self.get_key(key_id)
        if not api_key:
            return False
        
        await self.db.execute(
            update(APIKey)
            .where(APIKey.id == key_id)
            .values(
                is_active=False,
                revoked_at=datetime.utcnow(),
                revoked_by=revoked_by,
                revoked_reason=reason,
            )
        )
        
        logger.info(
            "API key revoked",
            key_id=str(key_id),
            revoked_by=str(revoked_by),
            reason=reason,
        )
        
        return True
    
    async def update_scopes(
        self,
        key_id: uuid.UUID,
        scopes: List[str],
    ) -> Optional[APIKey]:
        """Update the scopes of an API key."""
        # Validate scopes
        invalid_scopes = set(scopes) - set(STANDARD_SCOPES)
        if invalid_scopes:
            raise ValueError(f"Invalid scopes: {invalid_scopes}")
        
        await self.db.execute(
            update(APIKey)
            .where(APIKey.id == key_id)
            .values(scopes=scopes)
        )
        
        return await self.get_key(key_id)
    
    async def rotate_key(
        self,
        key_id: uuid.UUID,
        rotated_by: uuid.UUID,
    ) -> tuple[Optional[APIKey], Optional[str]]:
        """
        Rotate an API key (revoke old, create new with same config).
        
        Returns:
            Tuple of (new APIKey, new raw key) or (None, None) if not found
        """
        old_key = await self.get_key(key_id)
        if not old_key:
            return None, None
        
        # Create new key with same configuration
        new_key, raw_key = await self.create_key(
            name=old_key.name,
            created_by=rotated_by,
            scopes=old_key.scopes,
            description=f"Rotated from {old_key.key_prefix}. {old_key.description or ''}",
            expires_in_days=None,  # Will need to recalculate from original
            organization_id=old_key.organization_id,
            allowed_ips=old_key.allowed_ips,
            metadata={**(old_key.metadata or {}), "rotated_from": str(old_key.id)},
        )
        
        # Revoke old key
        await self.revoke_key(
            key_id=key_id,
            revoked_by=rotated_by,
            reason=f"Rotated to {new_key.key_prefix}",
        )
        
        logger.info(
            "API key rotated",
            old_key_id=str(key_id),
            new_key_id=str(new_key.id),
            rotated_by=str(rotated_by),
        )
        
        return new_key, raw_key
    
    @staticmethod
    def get_available_scopes() -> List[str]:
        """Get list of all available scopes."""
        return STANDARD_SCOPES.copy()
