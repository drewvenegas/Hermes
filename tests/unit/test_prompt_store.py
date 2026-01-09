"""
Tests for Prompt Store Service

Unit tests for prompt CRUD operations.
"""

import pytest
import uuid

from hermes.models import PromptType, PromptStatus
from hermes.schemas.prompt import PromptCreate, PromptUpdate, PromptQuery
from hermes.services.prompt_store import PromptStoreService


@pytest.mark.asyncio
async def test_create_prompt(db_session, sample_prompt_data, sample_user_id):
    """Test creating a new prompt."""
    service = PromptStoreService(db_session)
    
    data = PromptCreate(**sample_prompt_data)
    prompt = await service.create(data, owner_id=sample_user_id)
    
    assert prompt.id is not None
    assert prompt.slug == sample_prompt_data["slug"]
    assert prompt.name == sample_prompt_data["name"]
    assert prompt.type == PromptType.AGENT_SYSTEM
    assert prompt.status == PromptStatus.DRAFT
    assert prompt.version == "1.0.0"
    assert prompt.content_hash is not None


@pytest.mark.asyncio
async def test_get_prompt(db_session, sample_prompt_data, sample_user_id):
    """Test getting a prompt by ID."""
    service = PromptStoreService(db_session)
    
    data = PromptCreate(**sample_prompt_data)
    created = await service.create(data, owner_id=sample_user_id)
    
    prompt = await service.get(created.id)
    
    assert prompt is not None
    assert prompt.id == created.id
    assert prompt.slug == sample_prompt_data["slug"]


@pytest.mark.asyncio
async def test_get_prompt_by_slug(db_session, sample_prompt_data, sample_user_id):
    """Test getting a prompt by slug."""
    service = PromptStoreService(db_session)
    
    data = PromptCreate(**sample_prompt_data)
    await service.create(data, owner_id=sample_user_id)
    
    prompt = await service.get_by_slug(sample_prompt_data["slug"])
    
    assert prompt is not None
    assert prompt.slug == sample_prompt_data["slug"]


@pytest.mark.asyncio
async def test_get_nonexistent_prompt(db_session):
    """Test getting a nonexistent prompt."""
    service = PromptStoreService(db_session)
    
    prompt = await service.get(uuid.uuid4())
    
    assert prompt is None


@pytest.mark.asyncio
async def test_list_prompts(db_session, sample_prompt_data, sample_user_id):
    """Test listing prompts."""
    service = PromptStoreService(db_session)
    
    # Create multiple prompts
    for i in range(3):
        data = PromptCreate(**{**sample_prompt_data, "slug": f"test-prompt-{i}"})
        await service.create(data, owner_id=sample_user_id)
    
    query = PromptQuery()
    prompts, total = await service.list(query)
    
    assert len(prompts) == 3
    assert total == 3


@pytest.mark.asyncio
async def test_list_prompts_with_filter(db_session, sample_prompt_data, sample_user_id):
    """Test listing prompts with type filter."""
    service = PromptStoreService(db_session)
    
    # Create prompts of different types
    data1 = PromptCreate(**{**sample_prompt_data, "slug": "agent-1", "type": "agent_system"})
    data2 = PromptCreate(**{**sample_prompt_data, "slug": "template-1", "type": "user_template"})
    
    await service.create(data1, owner_id=sample_user_id)
    await service.create(data2, owner_id=sample_user_id)
    
    query = PromptQuery(type=PromptType.AGENT_SYSTEM)
    prompts, total = await service.list(query)
    
    assert len(prompts) == 1
    assert prompts[0].type == PromptType.AGENT_SYSTEM


@pytest.mark.asyncio
async def test_update_prompt(db_session, sample_prompt_data, sample_user_id):
    """Test updating a prompt."""
    service = PromptStoreService(db_session)
    
    data = PromptCreate(**sample_prompt_data)
    created = await service.create(data, owner_id=sample_user_id)
    
    update = PromptUpdate(name="Updated Name")
    updated = await service.update(created.id, update, author_id=sample_user_id)
    
    assert updated is not None
    assert updated.name == "Updated Name"
    assert updated.version == "1.0.0"  # No content change, version unchanged


@pytest.mark.asyncio
async def test_update_prompt_content_creates_version(db_session, sample_prompt_data, sample_user_id):
    """Test that updating content creates a new version."""
    service = PromptStoreService(db_session)
    
    data = PromptCreate(**sample_prompt_data)
    created = await service.create(data, owner_id=sample_user_id)
    
    update = PromptUpdate(content="You are an updated test assistant.")
    updated = await service.update(created.id, update, author_id=sample_user_id)
    
    assert updated is not None
    assert updated.version == "1.0.1"  # Version incremented


@pytest.mark.asyncio
async def test_delete_prompt(db_session, sample_prompt_data, sample_user_id):
    """Test deleting a prompt."""
    service = PromptStoreService(db_session)
    
    data = PromptCreate(**sample_prompt_data)
    created = await service.create(data, owner_id=sample_user_id)
    
    result = await service.delete(created.id)
    
    assert result is True
    
    prompt = await service.get(created.id)
    assert prompt is None


@pytest.mark.asyncio
async def test_delete_nonexistent_prompt(db_session):
    """Test deleting a nonexistent prompt."""
    service = PromptStoreService(db_session)
    
    result = await service.delete(uuid.uuid4())
    
    assert result is False


@pytest.mark.asyncio
async def test_compute_hash():
    """Test content hash computation."""
    content = "Test content"
    
    hash1 = PromptStoreService.compute_hash(content)
    hash2 = PromptStoreService.compute_hash(content)
    hash3 = PromptStoreService.compute_hash("Different content")
    
    assert hash1 == hash2
    assert hash1 != hash3
    assert len(hash1) == 64  # SHA-256 produces 64 hex characters
