"""
API Integration Tests

Tests for the Hermes REST API endpoints.
"""

import pytest


@pytest.mark.asyncio
async def test_health_check(client):
    """Test health check endpoint."""
    response = await client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "hermes"


@pytest.mark.asyncio
async def test_create_prompt(client, sample_prompt_data):
    """Test creating a prompt via API."""
    response = await client.post("/api/v1/prompts", json=sample_prompt_data)
    
    assert response.status_code == 201
    data = response.json()
    assert data["slug"] == sample_prompt_data["slug"]
    assert data["name"] == sample_prompt_data["name"]
    assert "id" in data


@pytest.mark.asyncio
async def test_create_duplicate_prompt(client, sample_prompt_data):
    """Test creating a duplicate prompt returns 409."""
    await client.post("/api/v1/prompts", json=sample_prompt_data)
    response = await client.post("/api/v1/prompts", json=sample_prompt_data)
    
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_get_prompt(client, sample_prompt_data):
    """Test getting a prompt by ID."""
    create_response = await client.post("/api/v1/prompts", json=sample_prompt_data)
    prompt_id = create_response.json()["id"]
    
    response = await client.get(f"/api/v1/prompts/{prompt_id}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == prompt_id


@pytest.mark.asyncio
async def test_get_prompt_not_found(client):
    """Test getting nonexistent prompt returns 404."""
    response = await client.get("/api/v1/prompts/00000000-0000-0000-0000-000000000000")
    
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_prompts(client, sample_prompt_data):
    """Test listing prompts."""
    await client.post("/api/v1/prompts", json=sample_prompt_data)
    
    response = await client.get("/api/v1/prompts")
    
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_update_prompt(client, sample_prompt_data):
    """Test updating a prompt."""
    create_response = await client.post("/api/v1/prompts", json=sample_prompt_data)
    prompt_id = create_response.json()["id"]
    
    response = await client.put(
        f"/api/v1/prompts/{prompt_id}",
        json={"name": "Updated Name"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_delete_prompt(client, sample_prompt_data):
    """Test deleting a prompt."""
    create_response = await client.post("/api/v1/prompts", json=sample_prompt_data)
    prompt_id = create_response.json()["id"]
    
    response = await client.delete(f"/api/v1/prompts/{prompt_id}")
    
    assert response.status_code == 204
    
    get_response = await client.get(f"/api/v1/prompts/{prompt_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_list_versions(client, sample_prompt_data):
    """Test listing prompt versions."""
    create_response = await client.post("/api/v1/prompts", json=sample_prompt_data)
    prompt_id = create_response.json()["id"]
    
    response = await client.get(f"/api/v1/prompts/{prompt_id}/versions")
    
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_run_benchmark(client, sample_prompt_data):
    """Test running a benchmark on a prompt."""
    create_response = await client.post("/api/v1/prompts", json=sample_prompt_data)
    prompt_id = create_response.json()["id"]
    
    response = await client.post(f"/api/v1/prompts/{prompt_id}/benchmark", json={})
    
    assert response.status_code == 200
    data = response.json()
    assert "overall_score" in data
    assert data["prompt_id"] == prompt_id
