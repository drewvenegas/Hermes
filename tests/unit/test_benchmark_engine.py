"""
Unit Tests for Benchmark Engine

Tests for the BenchmarkEngine service.
"""

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hermes.models.benchmark import BenchmarkResult
from hermes.models.prompt import Prompt, PromptType, PromptStatus


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return AsyncMock()


@pytest.fixture
def mock_prompt():
    """Create a mock prompt."""
    return Prompt(
        id=uuid.uuid4(),
        name="Test Prompt",
        slug="test-prompt",
        type=PromptType.USER_TEMPLATE,
        content="You are a helpful assistant.",
        version="1.0.0",
        status=PromptStatus.DEPLOYED,
        owner_id=uuid.uuid4(),
        is_latest=True,
    )


@pytest.fixture
def benchmark_engine(mock_db):
    """Create a benchmark engine instance."""
    from hermes.services.benchmark_engine import BenchmarkEngine
    return BenchmarkEngine(mock_db)


class TestBenchmarkEngine:
    """Tests for BenchmarkEngine."""
    
    @pytest.mark.asyncio
    async def test_run_benchmark_success(self, benchmark_engine, mock_prompt):
        """Test running a benchmark successfully."""
        with patch.object(benchmark_engine, '_run_ate_benchmark') as mock_ate:
            mock_ate.return_value = {
                "overall_score": 0.85,
                "dimension_scores": {
                    "clarity": 0.90,
                    "completeness": 0.80,
                    "accuracy": 0.85,
                },
                "execution_time_ms": 1500,
                "token_usage": {
                    "input_tokens": 100,
                    "output_tokens": 200,
                    "total_tokens": 300,
                },
            }
            
            result = await benchmark_engine.run_benchmark(
                prompt=mock_prompt,
                suite_id="default",
                model_id="aria01-d3n",
            )
            
            assert result is not None
            assert result.overall_score == 0.85
            assert "clarity" in result.dimension_scores
            mock_ate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_run_benchmark_with_baseline(self, benchmark_engine, mock_prompt):
        """Test benchmark calculates delta from baseline."""
        with patch.object(benchmark_engine, '_run_ate_benchmark') as mock_ate:
            mock_ate.return_value = {
                "overall_score": 0.90,
                "dimension_scores": {"clarity": 0.90},
                "execution_time_ms": 1000,
            }
            
            with patch.object(benchmark_engine, '_get_baseline_score') as mock_baseline:
                mock_baseline.return_value = 0.85
                
                result = await benchmark_engine.run_benchmark(
                    prompt=mock_prompt,
                    suite_id="default",
                    model_id="aria01-d3n",
                )
                
                assert result.baseline_score == 0.85
                assert result.delta == pytest.approx(0.05)
    
    @pytest.mark.asyncio
    async def test_run_benchmark_gate_check(self, benchmark_engine, mock_prompt):
        """Test quality gate is checked after benchmark."""
        with patch.object(benchmark_engine, '_run_ate_benchmark') as mock_ate:
            mock_ate.return_value = {
                "overall_score": 0.50,  # Below threshold
                "dimension_scores": {"clarity": 0.50},
                "execution_time_ms": 1000,
            }
            
            result = await benchmark_engine.run_benchmark(
                prompt=mock_prompt,
                suite_id="default",
                model_id="aria01-d3n",
            )
            
            assert result.gate_passed is False
    
    @pytest.mark.asyncio
    async def test_get_benchmark_history(self, benchmark_engine):
        """Test retrieving benchmark history."""
        prompt_id = uuid.uuid4()
        
        mock_results = [
            MagicMock(
                id=uuid.uuid4(),
                prompt_id=prompt_id,
                overall_score=0.85,
                executed_at=datetime.utcnow(),
            ),
            MagicMock(
                id=uuid.uuid4(),
                prompt_id=prompt_id,
                overall_score=0.80,
                executed_at=datetime.utcnow() - timedelta(days=1),
            ),
        ]
        
        with patch.object(benchmark_engine.db, 'execute') as mock_exec:
            mock_exec.return_value.scalars.return_value.all.return_value = mock_results
            
            history = await benchmark_engine.get_benchmark_history(prompt_id, limit=10)
            
            assert len(history) == 2
            assert history[0].overall_score == 0.85
    
    @pytest.mark.asyncio
    async def test_get_benchmark_trends_improving(self, benchmark_engine):
        """Test trend detection for improving scores."""
        prompt_id = uuid.uuid4()
        
        # Mock history with improving scores
        mock_results = []
        for i in range(10):
            mock_results.append(MagicMock(
                overall_score=0.70 + (i * 0.02),  # 0.70 to 0.88
                executed_at=datetime.utcnow() - timedelta(days=9-i),
                prompt_version=f"1.{i}.0",
            ))
        
        with patch.object(benchmark_engine, 'get_benchmark_history') as mock_history:
            mock_history.return_value = mock_results
            
            trends = await benchmark_engine.get_benchmark_trends(prompt_id, days=30)
            
            assert trends["trend"] == "improving"
            assert trends["change"] > 0
    
    @pytest.mark.asyncio
    async def test_get_benchmark_trends_declining(self, benchmark_engine):
        """Test trend detection for declining scores."""
        prompt_id = uuid.uuid4()
        
        # Mock history with declining scores
        mock_results = []
        for i in range(10):
            mock_results.append(MagicMock(
                overall_score=0.90 - (i * 0.02),  # 0.90 to 0.72
                executed_at=datetime.utcnow() - timedelta(days=9-i),
                prompt_version=f"1.{i}.0",
            ))
        
        with patch.object(benchmark_engine, 'get_benchmark_history') as mock_history:
            mock_history.return_value = mock_results
            
            trends = await benchmark_engine.get_benchmark_trends(prompt_id, days=30)
            
            assert trends["trend"] == "declining"
            assert trends["change"] < 0
    
    @pytest.mark.asyncio
    async def test_run_self_critique(self, benchmark_engine, mock_prompt):
        """Test running self-critique via ASRBS."""
        with patch.object(benchmark_engine, '_run_asrbs_critique') as mock_asrbs:
            mock_asrbs.return_value = {
                "overall_assessment": "Good prompt with room for improvement",
                "quality_score": 0.82,
                "suggestions": [
                    {
                        "id": "sug-1",
                        "category": "clarity",
                        "severity": "medium",
                        "description": "Add more specific examples",
                        "suggested_change": "Include concrete use cases",
                        "confidence": 0.85,
                    }
                ],
                "knowledge_gaps": ["domain-specific terminology"],
                "overconfidence_areas": [],
                "training_data_needs": [],
            }
            
            result = await benchmark_engine.run_self_critique(mock_prompt)
            
            assert result["quality_score"] == 0.82
            assert len(result["suggestions"]) == 1
            mock_asrbs.assert_called_once_with(mock_prompt)


class TestBenchmarkResultModel:
    """Tests for BenchmarkResult model."""
    
    def test_create_benchmark_result(self):
        """Test creating a benchmark result."""
        result = BenchmarkResult(
            id=uuid.uuid4(),
            prompt_id=uuid.uuid4(),
            prompt_version="1.0.0",
            suite_id="default",
            overall_score=0.85,
            dimension_scores={"clarity": 0.90, "completeness": 0.80},
            model_id="aria01-d3n",
            model_version="1.0",
            execution_time_ms=1500,
            executed_at=datetime.utcnow(),
        )
        
        assert result.overall_score == 0.85
        assert result.dimension_scores["clarity"] == 0.90
    
    def test_benchmark_result_to_dict(self):
        """Test converting benchmark result to dictionary."""
        result_id = uuid.uuid4()
        prompt_id = uuid.uuid4()
        
        result = BenchmarkResult(
            id=result_id,
            prompt_id=prompt_id,
            prompt_version="1.0.0",
            suite_id="default",
            overall_score=0.85,
            dimension_scores={"clarity": 0.90},
            model_id="aria01-d3n",
            execution_time_ms=1500,
            gate_passed=True,
            executed_at=datetime.utcnow(),
        )
        
        # If the model has a to_dict method
        if hasattr(result, 'to_dict'):
            data = result.to_dict()
            assert data["overall_score"] == 0.85
            assert data["gate_passed"] is True
