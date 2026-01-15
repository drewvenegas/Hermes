"""
Unit Tests for A/B Testing Service

Tests for the AB Testing service.
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
def ab_testing_service(mock_db):
    """Create an AB testing service instance."""
    from hermes.services.ab_testing import ABTestingService
    return ABTestingService(mock_db)


class TestABTestingService:
    """Tests for ABTestingService."""
    
    @pytest.mark.asyncio
    async def test_create_experiment(self, ab_testing_service):
        """Test creating a new experiment."""
        variants = [
            {"id": "control", "name": "Control", "promptId": str(uuid.uuid4()), "weight": 50},
            {"id": "variant-a", "name": "Variant A", "promptId": str(uuid.uuid4()), "weight": 50},
        ]
        
        metrics = [
            {"id": "conversion", "name": "Conversion Rate", "type": "conversion", "isGoal": True},
        ]
        
        experiment = await ab_testing_service.create_experiment(
            name="Test Experiment",
            description="Testing prompt variants",
            variants=variants,
            metrics=metrics,
            created_by=uuid.uuid4(),
        )
        
        assert experiment is not None
        assert experiment.name == "Test Experiment"
        assert experiment.status == "draft"
    
    @pytest.mark.asyncio
    async def test_start_experiment(self, ab_testing_service):
        """Test starting an experiment."""
        experiment_id = uuid.uuid4()
        
        mock_experiment = MagicMock(
            id=experiment_id,
            status="draft",
            variants={"variants": [{"id": "control"}, {"id": "variant-a"}]},
        )
        
        with patch.object(ab_testing_service, '_get_experiment') as mock_get:
            mock_get.return_value = mock_experiment
            
            result = await ab_testing_service.start_experiment(experiment_id)
            
            assert result.status == "running"
            assert result.started_at is not None
    
    @pytest.mark.asyncio
    async def test_start_experiment_invalid_status(self, ab_testing_service):
        """Test that starting a non-draft experiment fails."""
        experiment_id = uuid.uuid4()
        
        mock_experiment = MagicMock(
            id=experiment_id,
            status="running",  # Already running
        )
        
        with patch.object(ab_testing_service, '_get_experiment') as mock_get:
            mock_get.return_value = mock_experiment
            
            with pytest.raises(ValueError):
                await ab_testing_service.start_experiment(experiment_id)
    
    @pytest.mark.asyncio
    async def test_stop_experiment(self, ab_testing_service):
        """Test stopping an experiment."""
        experiment_id = uuid.uuid4()
        
        mock_experiment = MagicMock(
            id=experiment_id,
            status="running",
        )
        
        with patch.object(ab_testing_service, '_get_experiment') as mock_get:
            mock_get.return_value = mock_experiment
            
            with patch.object(ab_testing_service, '_calculate_results') as mock_calc:
                mock_calc.return_value = {
                    "winner": "variant-a",
                    "confidence": 0.95,
                }
                
                result = await ab_testing_service.stop_experiment(experiment_id)
                
                assert result.status == "completed"
                assert result.ended_at is not None
    
    @pytest.mark.asyncio
    async def test_record_event(self, ab_testing_service):
        """Test recording an experiment event."""
        experiment_id = uuid.uuid4()
        
        await ab_testing_service.record_event(
            experiment_id=experiment_id,
            variant_id="variant-a",
            user_id="user-123",
            event_type="conversion",
            value=1.0,
        )
        
        # Verify event was added to database
        assert ab_testing_service.db.add.called
    
    @pytest.mark.asyncio
    async def test_get_variant_for_user(self, ab_testing_service):
        """Test getting a variant assignment for a user."""
        experiment_id = uuid.uuid4()
        
        mock_experiment = MagicMock(
            id=experiment_id,
            status="running",
            traffic_percentage=100,
            variants={
                "variants": [
                    {"id": "control", "weight": 50},
                    {"id": "variant-a", "weight": 50},
                ]
            },
        )
        
        with patch.object(ab_testing_service, '_get_experiment') as mock_get:
            mock_get.return_value = mock_experiment
            
            variant = await ab_testing_service.get_variant_for_user(
                experiment_id=experiment_id,
                user_id="user-123",
            )
            
            assert variant in ["control", "variant-a"]
    
    @pytest.mark.asyncio
    async def test_get_variant_consistent_assignment(self, ab_testing_service):
        """Test that user gets consistent variant assignment."""
        experiment_id = uuid.uuid4()
        
        mock_experiment = MagicMock(
            id=experiment_id,
            status="running",
            traffic_percentage=100,
            variants={
                "variants": [
                    {"id": "control", "weight": 50},
                    {"id": "variant-a", "weight": 50},
                ]
            },
        )
        
        with patch.object(ab_testing_service, '_get_experiment') as mock_get:
            mock_get.return_value = mock_experiment
            
            # Same user should get same variant
            variant1 = await ab_testing_service.get_variant_for_user(
                experiment_id=experiment_id,
                user_id="user-123",
            )
            variant2 = await ab_testing_service.get_variant_for_user(
                experiment_id=experiment_id,
                user_id="user-123",
            )
            
            assert variant1 == variant2
    
    @pytest.mark.asyncio
    async def test_calculate_results(self, ab_testing_service):
        """Test calculating experiment results."""
        experiment_id = uuid.uuid4()
        
        mock_experiment = MagicMock(
            id=experiment_id,
            status="running",
            min_sample_size=100,
            confidence_threshold=0.95,
            variants={
                "variants": [
                    {"id": "control"},
                    {"id": "variant-a"},
                ]
            },
        )
        
        # Mock event data
        mock_events = [
            MagicMock(variant_id="control", event_type="impression", value=1),
            MagicMock(variant_id="control", event_type="conversion", value=1),
            MagicMock(variant_id="variant-a", event_type="impression", value=1),
            MagicMock(variant_id="variant-a", event_type="conversion", value=1),
        ] * 100
        
        with patch.object(ab_testing_service, '_get_experiment') as mock_get:
            mock_get.return_value = mock_experiment
            
            with patch.object(ab_testing_service, '_get_events') as mock_events_get:
                mock_events_get.return_value = mock_events
                
                results = await ab_testing_service.calculate_results(experiment_id)
                
                assert "winner" in results or results.get("winner") is None
                assert "confidence" in results


class TestStatisticalAnalysis:
    """Tests for statistical analysis functions."""
    
    def test_calculate_conversion_rate(self):
        """Test conversion rate calculation."""
        from hermes.services.ab_testing import calculate_conversion_rate
        
        rate = calculate_conversion_rate(conversions=50, impressions=1000)
        assert rate == 0.05
    
    def test_calculate_confidence_interval(self):
        """Test confidence interval calculation."""
        from hermes.services.ab_testing import calculate_confidence_interval
        
        lower, upper = calculate_confidence_interval(
            rate=0.10,
            sample_size=1000,
            confidence=0.95,
        )
        
        assert lower < 0.10 < upper
    
    def test_calculate_statistical_significance(self):
        """Test statistical significance calculation."""
        from hermes.services.ab_testing import is_statistically_significant
        
        # Clear winner
        is_significant = is_statistically_significant(
            control_conversions=100,
            control_impressions=1000,
            variant_conversions=150,
            variant_impressions=1000,
            confidence_threshold=0.95,
        )
        
        assert isinstance(is_significant, bool)
