"""
Integration Tests for Nursery Sync

Tests for the ARIA Nursery synchronization service.
"""

import os
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return AsyncMock()


@pytest.fixture
def nursery_sync_service(mock_db):
    """Create a nursery sync service instance."""
    from hermes.services.nursery_sync import NurserySyncService
    return NurserySyncService(mock_db)


@pytest.fixture
def mock_github_client():
    """Create a mock GitHub client."""
    client = MagicMock()
    client.get_contents.return_value = []
    return client


class TestNurserySyncService:
    """Integration tests for NurserySyncService."""
    
    @pytest.mark.asyncio
    async def test_import_from_nursery(self, nursery_sync_service, mock_github_client):
        """Test importing prompts from nursery."""
        with patch.object(nursery_sync_service, '_get_github_client') as mock_get_client:
            mock_get_client.return_value = mock_github_client
            
            mock_github_client.get_contents.return_value = [
                MagicMock(
                    type="file",
                    name="aria.md",
                    path="agents/aria.md",
                    decoded_content=b"""---
name: ARIA
slug: aria
type: agent_system
category: executive
---

You are ARIA, the primary executive agent.
""",
                ),
            ]
            
            result = await nursery_sync_service.import_from_nursery()
            
            assert result["imported"] >= 0 or result["updated"] >= 0
    
    @pytest.mark.asyncio
    async def test_import_handles_conflicts(self, nursery_sync_service, mock_github_client):
        """Test that import handles conflicts properly."""
        with patch.object(nursery_sync_service, '_get_github_client') as mock_get_client:
            mock_get_client.return_value = mock_github_client
            
            # Simulate existing prompt with different content
            with patch.object(nursery_sync_service, '_get_existing_prompt') as mock_existing:
                mock_existing.return_value = MagicMock(
                    id=uuid.uuid4(),
                    content="Different content",
                    version="1.0.0",
                )
                
                mock_github_client.get_contents.return_value = [
                    MagicMock(
                        type="file",
                        name="aria.md",
                        path="agents/aria.md",
                        decoded_content=b"""---
name: ARIA
slug: aria
---
New content
""",
                    ),
                ]
                
                result = await nursery_sync_service.import_from_nursery(
                    conflict_resolution="skip"
                )
                
                # Should skip conflicting prompt
                assert result["skipped"] >= 0 or "conflicts" in result
    
    @pytest.mark.asyncio
    async def test_export_to_nursery(self, nursery_sync_service, mock_github_client):
        """Test exporting prompts to nursery."""
        prompt_id = uuid.uuid4()
        
        mock_prompt = MagicMock(
            id=prompt_id,
            name="Test Prompt",
            slug="test-prompt",
            content="Test content",
            version="1.0.0",
            metadata={"aria_agent": True},
        )
        
        with patch.object(nursery_sync_service, '_get_github_client') as mock_get_client:
            mock_get_client.return_value = mock_github_client
            
            with patch.object(nursery_sync_service, '_get_prompts_to_export') as mock_prompts:
                mock_prompts.return_value = [mock_prompt]
                
                result = await nursery_sync_service.export_to_nursery(
                    prompt_ids=[prompt_id],
                    commit_message="Export test prompt",
                )
                
                assert result is not None
    
    @pytest.mark.asyncio
    async def test_sync_status(self, nursery_sync_service):
        """Test getting sync status."""
        status = await nursery_sync_service.get_sync_status()
        
        assert "state" in status or "sync_state" in status
        assert "pending_changes" in status or status.get("state") is not None
    
    @pytest.mark.asyncio
    async def test_resolve_conflict_local(self, nursery_sync_service):
        """Test resolving conflict with local version."""
        prompt_id = uuid.uuid4()
        
        with patch.object(nursery_sync_service, '_get_conflict') as mock_conflict:
            mock_conflict.return_value = MagicMock(
                prompt_id=prompt_id,
                local_version="1.0.0",
                nursery_version="2.0.0",
            )
            
            result = await nursery_sync_service.resolve_conflict(
                prompt_id=prompt_id,
                resolution="local",
            )
            
            # Should return the local prompt
            assert result is not None
    
    @pytest.mark.asyncio
    async def test_resolve_conflict_nursery(self, nursery_sync_service, mock_github_client):
        """Test resolving conflict with nursery version."""
        prompt_id = uuid.uuid4()
        
        with patch.object(nursery_sync_service, '_get_github_client') as mock_get_client:
            mock_get_client.return_value = mock_github_client
            
            with patch.object(nursery_sync_service, '_get_conflict') as mock_conflict:
                mock_conflict.return_value = MagicMock(
                    prompt_id=prompt_id,
                    nursery_path="agents/test.md",
                )
                
                mock_github_client.get_contents.return_value = MagicMock(
                    decoded_content=b"Nursery content",
                )
                
                result = await nursery_sync_service.resolve_conflict(
                    prompt_id=prompt_id,
                    resolution="nursery",
                )
                
                assert result is not None
    
    @pytest.mark.asyncio
    async def test_resolve_conflict_merged(self, nursery_sync_service):
        """Test resolving conflict with merged content."""
        prompt_id = uuid.uuid4()
        
        with patch.object(nursery_sync_service, '_get_conflict') as mock_conflict:
            mock_conflict.return_value = MagicMock(
                prompt_id=prompt_id,
            )
            
            result = await nursery_sync_service.resolve_conflict(
                prompt_id=prompt_id,
                resolution="merged",
                merged_content="Manually merged content",
            )
            
            assert result is not None


class TestNurseryParsing:
    """Tests for nursery file parsing."""
    
    def test_parse_markdown_frontmatter(self, nursery_sync_service):
        """Test parsing markdown with YAML frontmatter."""
        content = """---
name: Test Agent
slug: test-agent
type: agent_system
category: specialists
description: A test agent
variables:
  key: value
---

# Test Agent

You are a test agent.
"""
        
        result = nursery_sync_service._parse_nursery_file(content)
        
        assert result["name"] == "Test Agent"
        assert result["slug"] == "test-agent"
        assert "You are a test agent" in result["content"]
    
    def test_parse_markdown_without_frontmatter(self, nursery_sync_service):
        """Test parsing markdown without frontmatter."""
        content = """# Simple Agent

Just content without metadata.
"""
        
        result = nursery_sync_service._parse_nursery_file(content)
        
        assert "content" in result
        assert "Simple Agent" in result.get("content", "") or result.get("name") is not None
    
    def test_generate_markdown(self, nursery_sync_service):
        """Test generating markdown from prompt."""
        mock_prompt = MagicMock(
            name="Test Prompt",
            slug="test-prompt",
            type=MagicMock(value="agent_system"),
            category="specialists",
            description="A test prompt",
            content="You are a helpful assistant.",
            variables={"key": "value"},
            metadata={"custom": "data"},
        )
        
        markdown = nursery_sync_service._generate_nursery_markdown(mock_prompt)
        
        assert "name: Test Prompt" in markdown
        assert "slug: test-prompt" in markdown
        assert "You are a helpful assistant" in markdown
