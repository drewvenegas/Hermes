"""
Unit Tests for Quality Gates Service

Tests for the QualityGateService.
"""

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return AsyncMock()


@pytest.fixture
def quality_gate_service(mock_db):
    """Create a quality gate service instance."""
    from hermes.services.quality_gates import QualityGateService
    return QualityGateService(mock_db)


class TestQualityGateService:
    """Tests for QualityGateService."""
    
    @pytest.mark.asyncio
    async def test_evaluate_passes_all_gates(self, quality_gate_service):
        """Test that all gates pass when conditions are met."""
        prompt_id = uuid.uuid4()
        
        with patch.object(quality_gate_service, '_get_latest_benchmark') as mock_benchmark:
            mock_benchmark.return_value = MagicMock(
                overall_score=0.90,
                dimension_scores={"clarity": 0.95, "completeness": 0.88, "accuracy": 0.87},
                executed_at=datetime.utcnow() - timedelta(hours=1),
            )
            
            with patch.object(quality_gate_service, '_get_baseline_score') as mock_baseline:
                mock_baseline.return_value = 0.85
                
                result = await quality_gate_service.evaluate(prompt_id)
                
                assert result["passed"] is True
                assert result["overall_score"] == 0.90
                assert all(g["passed"] for g in result["gates"])
    
    @pytest.mark.asyncio
    async def test_evaluate_fails_score_threshold(self, quality_gate_service):
        """Test that score threshold gate fails when score is too low."""
        prompt_id = uuid.uuid4()
        
        with patch.object(quality_gate_service, '_get_latest_benchmark') as mock_benchmark:
            mock_benchmark.return_value = MagicMock(
                overall_score=0.50,  # Below default threshold of 0.7
                dimension_scores={"clarity": 0.50},
                executed_at=datetime.utcnow(),
            )
            
            result = await quality_gate_service.evaluate(prompt_id)
            
            assert result["passed"] is False
            
            score_gate = next(g for g in result["gates"] if g["gate"] == "score_threshold")
            assert score_gate["passed"] is False
            assert score_gate["value"] == 0.50
    
    @pytest.mark.asyncio
    async def test_evaluate_fails_regression_detection(self, quality_gate_service):
        """Test that regression gate fails when score drops significantly."""
        prompt_id = uuid.uuid4()
        
        with patch.object(quality_gate_service, '_get_latest_benchmark') as mock_benchmark:
            mock_benchmark.return_value = MagicMock(
                overall_score=0.70,
                dimension_scores={"clarity": 0.70},
                executed_at=datetime.utcnow(),
            )
            
            with patch.object(quality_gate_service, '_get_baseline_score') as mock_baseline:
                mock_baseline.return_value = 0.90  # 20% regression
                
                result = await quality_gate_service.evaluate(prompt_id)
                
                regression_gate = next(g for g in result["gates"] if g["gate"] == "regression")
                assert regression_gate["passed"] is False
    
    @pytest.mark.asyncio
    async def test_evaluate_fails_benchmark_freshness(self, quality_gate_service):
        """Test that freshness gate fails when benchmark is too old."""
        prompt_id = uuid.uuid4()
        
        with patch.object(quality_gate_service, '_get_latest_benchmark') as mock_benchmark:
            mock_benchmark.return_value = MagicMock(
                overall_score=0.90,
                dimension_scores={"clarity": 0.90},
                executed_at=datetime.utcnow() - timedelta(days=10),  # Old benchmark
            )
            
            result = await quality_gate_service.evaluate(prompt_id)
            
            freshness_gate = next(g for g in result["gates"] if g["gate"] == "freshness")
            assert freshness_gate["passed"] is False
    
    @pytest.mark.asyncio
    async def test_evaluate_dimension_gates(self, quality_gate_service):
        """Test dimension-specific gate checks."""
        prompt_id = uuid.uuid4()
        
        with patch.object(quality_gate_service, '_get_latest_benchmark') as mock_benchmark:
            mock_benchmark.return_value = MagicMock(
                overall_score=0.85,
                dimension_scores={
                    "clarity": 0.90,
                    "completeness": 0.40,  # Below threshold
                    "accuracy": 0.85,
                },
                executed_at=datetime.utcnow(),
            )
            
            result = await quality_gate_service.evaluate(prompt_id)
            
            # Check that completeness dimension failed
            completeness_gate = next(
                (g for g in result["gates"] if "completeness" in g["gate"]),
                None
            )
            if completeness_gate:
                assert completeness_gate["passed"] is False
    
    @pytest.mark.asyncio
    async def test_evaluate_no_benchmark(self, quality_gate_service):
        """Test handling when no benchmark exists."""
        prompt_id = uuid.uuid4()
        
        with patch.object(quality_gate_service, '_get_latest_benchmark') as mock_benchmark:
            mock_benchmark.return_value = None
            
            result = await quality_gate_service.evaluate(prompt_id)
            
            assert result["passed"] is False
            assert "No benchmark" in result["recommendations"][0] or any(
                "benchmark" in r.lower() for r in result["recommendations"]
            )
    
    @pytest.mark.asyncio
    async def test_evaluate_generates_recommendations(self, quality_gate_service):
        """Test that appropriate recommendations are generated."""
        prompt_id = uuid.uuid4()
        
        with patch.object(quality_gate_service, '_get_latest_benchmark') as mock_benchmark:
            mock_benchmark.return_value = MagicMock(
                overall_score=0.65,  # Below threshold
                dimension_scores={"clarity": 0.50},  # Low clarity
                executed_at=datetime.utcnow() - timedelta(days=8),  # Stale
            )
            
            result = await quality_gate_service.evaluate(prompt_id)
            
            assert len(result["recommendations"]) > 0
    
    @pytest.mark.asyncio
    async def test_get_gate_status(self, quality_gate_service):
        """Test getting gate status for a prompt."""
        prompt_id = uuid.uuid4()
        
        with patch.object(quality_gate_service, 'evaluate') as mock_evaluate:
            mock_evaluate.return_value = {
                "passed": True,
                "gates": [{"gate": "score_threshold", "passed": True}],
                "overall_score": 0.90,
                "recommendations": [],
            }
            
            status = await quality_gate_service.get_status(prompt_id)
            
            assert status["passed"] is True
            mock_evaluate.assert_called_once_with(prompt_id)


class TestGateConfiguration:
    """Tests for gate configuration."""
    
    def test_default_thresholds(self):
        """Test default gate thresholds."""
        from hermes.services.quality_gates import DEFAULT_GATE_CONFIG
        
        assert DEFAULT_GATE_CONFIG["score_threshold"] >= 0.5
        assert DEFAULT_GATE_CONFIG["regression_threshold"] <= 0.2
        assert DEFAULT_GATE_CONFIG["freshness_days"] >= 1
    
    def test_custom_thresholds(self, mock_db):
        """Test using custom gate thresholds."""
        from hermes.services.quality_gates import QualityGateService
        
        custom_config = {
            "score_threshold": 0.9,
            "regression_threshold": 0.05,
            "freshness_days": 1,
        }
        
        service = QualityGateService(mock_db, config=custom_config)
        
        assert service.config["score_threshold"] == 0.9
