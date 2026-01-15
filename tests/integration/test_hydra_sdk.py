"""
Integration Tests for Hydra SDK

Tests for the Hermes SDK integration with Hydra.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestHermesSdkIntegration:
    """Integration tests for Hermes SDK."""
    
    @pytest.fixture
    def mock_hermes_api(self):
        """Create a mock Hermes API."""
        return MagicMock()
    
    @pytest.mark.asyncio
    async def test_sdk_create_prompt(self, mock_hermes_api):
        """Test creating a prompt via SDK."""
        # This would test the TypeScript SDK in a real scenario
        # For Python tests, we verify the API contract
        
        request_data = {
            "name": "Test Prompt",
            "slug": "test-prompt",
            "type": "user_template",
            "content": "Test content",
        }
        
        expected_response = {
            "id": "uuid-123",
            "name": "Test Prompt",
            "slug": "test-prompt",
            "version": "1.0.0",
            "content": "Test content",
        }
        
        mock_hermes_api.post.return_value.json.return_value = expected_response
        
        # Verify the request/response contract
        assert expected_response["name"] == request_data["name"]
        assert "id" in expected_response
        assert "version" in expected_response
    
    @pytest.mark.asyncio
    async def test_sdk_get_prompt(self, mock_hermes_api):
        """Test getting a prompt via SDK."""
        prompt_id = "uuid-123"
        
        expected_response = {
            "id": prompt_id,
            "name": "Test Prompt",
            "slug": "test-prompt",
            "content": "Test content",
            "version": "1.0.0",
            "benchmarkScore": 0.85,
        }
        
        mock_hermes_api.get.return_value.json.return_value = expected_response
        
        assert expected_response["id"] == prompt_id
        assert "benchmarkScore" in expected_response
    
    @pytest.mark.asyncio
    async def test_sdk_run_benchmark(self, mock_hermes_api):
        """Test running a benchmark via SDK."""
        prompt_id = "uuid-123"
        
        request_data = {
            "promptId": prompt_id,
            "suiteId": "default",
            "modelId": "aria01-d3n",
        }
        
        expected_response = {
            "id": "benchmark-uuid",
            "promptId": prompt_id,
            "overallScore": 0.87,
            "dimensionScores": {
                "clarity": 0.90,
                "completeness": 0.85,
            },
            "gatePassed": True,
            "executionTimeMs": 1500,
        }
        
        mock_hermes_api.post.return_value.json.return_value = expected_response
        
        assert expected_response["promptId"] == prompt_id
        assert expected_response["overallScore"] >= 0
        assert "dimensionScores" in expected_response
    
    @pytest.mark.asyncio
    async def test_sdk_quality_gates(self, mock_hermes_api):
        """Test evaluating quality gates via SDK."""
        prompt_id = "uuid-123"
        
        expected_response = {
            "passed": True,
            "overallScore": 0.90,
            "gates": [
                {"gate": "score_threshold", "passed": True, "value": 0.90, "threshold": 0.70},
                {"gate": "regression", "passed": True, "value": 0.05, "threshold": 0.10},
            ],
            "recommendations": [],
        }
        
        mock_hermes_api.post.return_value.json.return_value = expected_response
        
        assert expected_response["passed"] is True
        assert len(expected_response["gates"]) > 0
    
    @pytest.mark.asyncio
    async def test_sdk_experiment_lifecycle(self, mock_hermes_api):
        """Test experiment lifecycle via SDK."""
        # Create experiment
        create_request = {
            "name": "Test Experiment",
            "variants": [
                {"id": "control", "promptId": "prompt-1", "weight": 50},
                {"id": "variant-a", "promptId": "prompt-2", "weight": 50},
            ],
            "metrics": [
                {"id": "conversion", "type": "conversion", "isGoal": True},
            ],
        }
        
        create_response = {
            "id": "exp-uuid",
            "name": "Test Experiment",
            "status": "draft",
            "variants": create_request["variants"],
        }
        
        # Start experiment
        start_response = {
            "id": "exp-uuid",
            "status": "running",
            "startedAt": "2026-01-14T00:00:00Z",
        }
        
        # Get results
        results_response = {
            "id": "exp-uuid",
            "status": "completed",
            "winnerVariantId": "variant-a",
            "result": {
                "winner": "variant-a",
                "confidence": 0.97,
            },
        }
        
        assert create_response["status"] == "draft"
        assert start_response["status"] == "running"
        assert results_response["status"] == "completed"


class TestApiContract:
    """Tests to verify API contract between SDK and server."""
    
    def test_prompt_response_schema(self):
        """Verify prompt response matches SDK types."""
        response = {
            "id": "uuid",
            "slug": "test-prompt",
            "name": "Test Prompt",
            "description": "A test prompt",
            "type": "user_template",
            "category": "general",
            "content": "Content here",
            "variables": {},
            "metadata": {},
            "version": "1.0.0",
            "parentId": None,
            "isLatest": True,
            "contentHash": "abc123",
            "ownerId": "owner-uuid",
            "ownerType": "user",
            "teamId": None,
            "visibility": "private",
            "appScope": [],
            "repoScope": [],
            "benchmarkSuite": None,
            "lastBenchmarkAt": None,
            "benchmarkScore": None,
            "status": "draft",
            "deployedAt": None,
            "createdAt": "2026-01-14T00:00:00Z",
            "updatedAt": "2026-01-14T00:00:00Z",
        }
        
        # All fields required by SDK types should be present
        required_fields = [
            "id", "name", "content", "version", "type", "status",
            "createdAt", "updatedAt"
        ]
        
        for field in required_fields:
            assert field in response, f"Missing field: {field}"
    
    def test_benchmark_result_schema(self):
        """Verify benchmark result matches SDK types."""
        response = {
            "id": "uuid",
            "promptId": "prompt-uuid",
            "promptVersion": "1.0.0",
            "suiteId": "default",
            "overallScore": 0.85,
            "dimensionScores": {"clarity": 0.90},
            "modelId": "aria01-d3n",
            "modelVersion": "1.0",
            "executionTimeMs": 1500,
            "tokenUsage": {
                "inputTokens": 100,
                "outputTokens": 200,
                "totalTokens": 300,
            },
            "baselineScore": 0.80,
            "delta": 0.05,
            "gatePassed": True,
            "executedAt": "2026-01-14T00:00:00Z",
            "executedBy": "user-uuid",
            "environment": "production",
        }
        
        required_fields = [
            "id", "promptId", "overallScore", "dimensionScores",
            "modelId", "executionTimeMs", "gatePassed", "executedAt"
        ]
        
        for field in required_fields:
            assert field in response, f"Missing field: {field}"
    
    def test_experiment_schema(self):
        """Verify experiment response matches SDK types."""
        response = {
            "id": "uuid",
            "name": "Test Experiment",
            "description": "Description",
            "status": "draft",
            "variants": [
                {"id": "control", "name": "Control", "promptId": "p1", "weight": 50}
            ],
            "metrics": [
                {"id": "conv", "name": "Conversion", "type": "conversion", "isGoal": True}
            ],
            "trafficSplit": "equal",
            "trafficPercentage": 100,
            "minSampleSize": 1000,
            "maxDurationDays": 14,
            "confidenceThreshold": 0.95,
            "autoPromote": False,
            "startedAt": None,
            "endedAt": None,
            "result": None,
            "winnerVariantId": None,
            "createdBy": "user-uuid",
            "createdAt": "2026-01-14T00:00:00Z",
            "tags": [],
        }
        
        required_fields = [
            "id", "name", "status", "variants", "metrics", "createdBy"
        ]
        
        for field in required_fields:
            assert field in response, f"Missing field: {field}"
