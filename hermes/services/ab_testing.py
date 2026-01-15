"""
A/B Testing Service

Framework for running prompt experiments and optimization.
Features:
- Experiment creation and management
- Traffic splitting
- Statistical analysis
- Winner detection
- Auto-promotion
"""

import asyncio
import hashlib
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from hermes.config import get_settings
from hermes.models import Prompt

settings = get_settings()
logger = structlog.get_logger()


class ExperimentStatus(str, Enum):
    """Experiment lifecycle status."""
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TrafficSplitStrategy(str, Enum):
    """Traffic splitting strategy."""
    EQUAL = "equal"  # Equal distribution
    WEIGHTED = "weighted"  # Custom weights
    EPSILON_GREEDY = "epsilon_greedy"  # Explore/exploit
    THOMPSON_SAMPLING = "thompson_sampling"  # Bayesian
    UCB = "ucb"  # Upper confidence bound


class MetricType(str, Enum):
    """Types of metrics to track."""
    CONVERSION = "conversion"  # Binary outcome
    VALUE = "value"  # Numeric value
    RATING = "rating"  # 1-5 rating
    LATENCY = "latency"  # Time in ms


@dataclass
class ExperimentVariant:
    """A variant in an A/B experiment."""
    id: str
    name: str
    prompt_id: uuid.UUID
    prompt_version: str
    weight: float = 0.5  # Traffic allocation weight
    is_control: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExperimentMetric:
    """Metric configuration for an experiment."""
    id: str
    name: str
    type: MetricType
    goal: str = "maximize"  # maximize or minimize
    minimum_detectable_effect: float = 0.05  # 5%
    is_primary: bool = False


@dataclass
class VariantStats:
    """Statistics for a variant."""
    variant_id: str
    impressions: int = 0
    conversions: int = 0
    total_value: float = 0.0
    total_latency: float = 0.0
    
    @property
    def conversion_rate(self) -> float:
        return self.conversions / self.impressions if self.impressions > 0 else 0.0
    
    @property
    def mean_value(self) -> float:
        return self.total_value / self.impressions if self.impressions > 0 else 0.0
    
    @property
    def mean_latency(self) -> float:
        return self.total_latency / self.impressions if self.impressions > 0 else 0.0


@dataclass
class ExperimentResult:
    """Final result of an experiment."""
    experiment_id: uuid.UUID
    winner_variant_id: Optional[str]
    confidence: float
    lift: float  # Percentage improvement
    is_significant: bool
    metrics: Dict[str, Dict[str, float]]
    recommendation: str
    completed_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Experiment:
    """An A/B experiment."""
    id: uuid.UUID
    name: str
    description: str
    status: ExperimentStatus
    variants: List[ExperimentVariant]
    metrics: List[ExperimentMetric]
    traffic_split: TrafficSplitStrategy
    traffic_percentage: float  # % of total traffic in experiment
    
    # Configuration
    min_sample_size: int = 1000
    max_duration_days: int = 14
    confidence_threshold: float = 0.95
    auto_promote: bool = False
    
    # State
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    
    # Results
    variant_stats: Dict[str, VariantStats] = field(default_factory=dict)
    result: Optional[ExperimentResult] = None
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "variants": [
                {
                    "id": v.id,
                    "name": v.name,
                    "prompt_id": str(v.prompt_id),
                    "prompt_version": v.prompt_version,
                    "weight": v.weight,
                    "is_control": v.is_control,
                }
                for v in self.variants
            ],
            "metrics": [
                {
                    "id": m.id,
                    "name": m.name,
                    "type": m.type.value,
                    "is_primary": m.is_primary,
                }
                for m in self.metrics
            ],
            "traffic_split": self.traffic_split.value,
            "traffic_percentage": self.traffic_percentage,
            "min_sample_size": self.min_sample_size,
            "max_duration_days": self.max_duration_days,
            "confidence_threshold": self.confidence_threshold,
            "auto_promote": self.auto_promote,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
        }


class ABTestingService:
    """
    Service for managing A/B experiments on prompts.
    
    Features:
    - Create and manage experiments
    - Traffic splitting with multiple strategies
    - Real-time metrics collection
    - Statistical significance testing
    - Automatic winner detection
    - Auto-promotion of winning variants
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self._experiments: Dict[uuid.UUID, Experiment] = {}
        self._active_experiments: Dict[uuid.UUID, Experiment] = {}  # By prompt_id
    
    # =========================================================================
    # Experiment Management
    # =========================================================================
    
    async def create_experiment(
        self,
        name: str,
        description: str,
        variants: List[Dict[str, Any]],
        metrics: List[Dict[str, Any]],
        traffic_split: TrafficSplitStrategy = TrafficSplitStrategy.EQUAL,
        traffic_percentage: float = 100.0,
        min_sample_size: int = 1000,
        max_duration_days: int = 14,
        confidence_threshold: float = 0.95,
        auto_promote: bool = False,
    ) -> Experiment:
        """Create a new A/B experiment."""
        experiment_id = uuid.uuid4()
        
        # Create variant objects
        experiment_variants = []
        for i, v in enumerate(variants):
            variant = ExperimentVariant(
                id=v.get("id", f"variant_{i}"),
                name=v["name"],
                prompt_id=uuid.UUID(v["prompt_id"]),
                prompt_version=v.get("prompt_version", "latest"),
                weight=v.get("weight", 1.0 / len(variants)),
                is_control=v.get("is_control", i == 0),
                metadata=v.get("metadata", {}),
            )
            experiment_variants.append(variant)
        
        # Normalize weights
        total_weight = sum(v.weight for v in experiment_variants)
        for v in experiment_variants:
            v.weight = v.weight / total_weight
        
        # Create metric objects
        experiment_metrics = []
        for i, m in enumerate(metrics):
            metric = ExperimentMetric(
                id=m.get("id", f"metric_{i}"),
                name=m["name"],
                type=MetricType(m.get("type", "conversion")),
                goal=m.get("goal", "maximize"),
                minimum_detectable_effect=m.get("mde", 0.05),
                is_primary=m.get("is_primary", i == 0),
            )
            experiment_metrics.append(metric)
        
        experiment = Experiment(
            id=experiment_id,
            name=name,
            description=description,
            status=ExperimentStatus.DRAFT,
            variants=experiment_variants,
            metrics=experiment_metrics,
            traffic_split=traffic_split,
            traffic_percentage=traffic_percentage,
            min_sample_size=min_sample_size,
            max_duration_days=max_duration_days,
            confidence_threshold=confidence_threshold,
            auto_promote=auto_promote,
        )
        
        # Initialize stats for each variant
        for v in experiment_variants:
            experiment.variant_stats[v.id] = VariantStats(variant_id=v.id)
        
        self._experiments[experiment_id] = experiment
        
        logger.info(
            "Experiment created",
            experiment_id=str(experiment_id),
            name=name,
            variants=len(variants),
        )
        
        return experiment
    
    async def start_experiment(self, experiment_id: uuid.UUID) -> Experiment:
        """Start an experiment."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")
        
        if experiment.status != ExperimentStatus.DRAFT:
            raise ValueError(f"Cannot start experiment in {experiment.status} status")
        
        experiment.status = ExperimentStatus.RUNNING
        experiment.started_at = datetime.utcnow()
        
        # Register active experiment for each variant's prompt
        for variant in experiment.variants:
            self._active_experiments[variant.prompt_id] = experiment
        
        logger.info(
            "Experiment started",
            experiment_id=str(experiment_id),
            name=experiment.name,
        )
        
        return experiment
    
    async def pause_experiment(self, experiment_id: uuid.UUID) -> Experiment:
        """Pause a running experiment."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")
        
        experiment.status = ExperimentStatus.PAUSED
        
        logger.info("Experiment paused", experiment_id=str(experiment_id))
        
        return experiment
    
    async def resume_experiment(self, experiment_id: uuid.UUID) -> Experiment:
        """Resume a paused experiment."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")
        
        if experiment.status != ExperimentStatus.PAUSED:
            raise ValueError("Can only resume paused experiments")
        
        experiment.status = ExperimentStatus.RUNNING
        
        logger.info("Experiment resumed", experiment_id=str(experiment_id))
        
        return experiment
    
    async def stop_experiment(
        self,
        experiment_id: uuid.UUID,
        compute_results: bool = True,
    ) -> Experiment:
        """Stop an experiment and optionally compute final results."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")
        
        experiment.status = ExperimentStatus.COMPLETED
        experiment.ended_at = datetime.utcnow()
        
        # Remove from active experiments
        for variant in experiment.variants:
            if variant.prompt_id in self._active_experiments:
                del self._active_experiments[variant.prompt_id]
        
        if compute_results:
            experiment.result = await self._compute_results(experiment)
        
        logger.info(
            "Experiment stopped",
            experiment_id=str(experiment_id),
            winner=experiment.result.winner_variant_id if experiment.result else None,
        )
        
        return experiment
    
    async def get_experiment(self, experiment_id: uuid.UUID) -> Optional[Experiment]:
        """Get an experiment by ID."""
        return self._experiments.get(experiment_id)
    
    async def list_experiments(
        self,
        status: ExperimentStatus = None,
        prompt_id: uuid.UUID = None,
    ) -> List[Experiment]:
        """List experiments with optional filtering."""
        experiments = list(self._experiments.values())
        
        if status:
            experiments = [e for e in experiments if e.status == status]
        
        if prompt_id:
            experiments = [
                e for e in experiments
                if any(v.prompt_id == prompt_id for v in e.variants)
            ]
        
        return sorted(experiments, key=lambda e: e.created_at, reverse=True)
    
    # =========================================================================
    # Traffic Assignment
    # =========================================================================
    
    async def assign_variant(
        self,
        prompt_id: uuid.UUID,
        user_id: str,
        context: Dict[str, Any] = None,
    ) -> Optional[ExperimentVariant]:
        """
        Assign a variant for a user/request.
        
        Args:
            prompt_id: The prompt being requested
            user_id: Unique user identifier (for consistent assignment)
            context: Additional context for assignment
            
        Returns:
            Assigned variant or None if not in experiment
        """
        experiment = self._active_experiments.get(prompt_id)
        if not experiment or experiment.status != ExperimentStatus.RUNNING:
            return None
        
        # Check if within traffic percentage
        traffic_hash = self._hash_for_traffic(user_id, str(experiment.id))
        if traffic_hash > experiment.traffic_percentage / 100:
            return None
        
        # Assign variant based on strategy
        if experiment.traffic_split == TrafficSplitStrategy.EQUAL:
            variant = self._assign_equal(experiment, user_id)
        elif experiment.traffic_split == TrafficSplitStrategy.WEIGHTED:
            variant = self._assign_weighted(experiment, user_id)
        elif experiment.traffic_split == TrafficSplitStrategy.EPSILON_GREEDY:
            variant = self._assign_epsilon_greedy(experiment, user_id)
        elif experiment.traffic_split == TrafficSplitStrategy.THOMPSON_SAMPLING:
            variant = self._assign_thompson(experiment)
        elif experiment.traffic_split == TrafficSplitStrategy.UCB:
            variant = self._assign_ucb(experiment)
        else:
            variant = self._assign_equal(experiment, user_id)
        
        return variant
    
    def _hash_for_traffic(self, user_id: str, experiment_id: str) -> float:
        """Generate consistent hash for traffic assignment."""
        h = hashlib.md5(f"{user_id}:{experiment_id}".encode()).hexdigest()
        return int(h[:8], 16) / 0xFFFFFFFF
    
    def _hash_for_variant(self, user_id: str, experiment_id: str) -> float:
        """Generate consistent hash for variant assignment."""
        h = hashlib.md5(f"variant:{user_id}:{experiment_id}".encode()).hexdigest()
        return int(h[:8], 16) / 0xFFFFFFFF
    
    def _assign_equal(
        self,
        experiment: Experiment,
        user_id: str,
    ) -> ExperimentVariant:
        """Assign with equal distribution."""
        hash_val = self._hash_for_variant(user_id, str(experiment.id))
        n_variants = len(experiment.variants)
        index = int(hash_val * n_variants)
        return experiment.variants[index]
    
    def _assign_weighted(
        self,
        experiment: Experiment,
        user_id: str,
    ) -> ExperimentVariant:
        """Assign based on configured weights."""
        hash_val = self._hash_for_variant(user_id, str(experiment.id))
        cumulative = 0.0
        for variant in experiment.variants:
            cumulative += variant.weight
            if hash_val < cumulative:
                return variant
        return experiment.variants[-1]
    
    def _assign_epsilon_greedy(
        self,
        experiment: Experiment,
        user_id: str,
        epsilon: float = 0.1,
    ) -> ExperimentVariant:
        """Epsilon-greedy: explore with probability epsilon."""
        import random
        
        if random.random() < epsilon:
            # Explore: random variant
            return random.choice(experiment.variants)
        else:
            # Exploit: best performing variant
            best_variant = max(
                experiment.variants,
                key=lambda v: experiment.variant_stats[v.id].conversion_rate
            )
            return best_variant
    
    def _assign_thompson(self, experiment: Experiment) -> ExperimentVariant:
        """Thompson sampling: sample from posterior distributions."""
        import random
        
        samples = []
        for variant in experiment.variants:
            stats = experiment.variant_stats[variant.id]
            # Beta distribution with Laplace smoothing
            alpha = stats.conversions + 1
            beta = stats.impressions - stats.conversions + 1
            sample = random.betavariate(alpha, beta)
            samples.append((variant, sample))
        
        return max(samples, key=lambda x: x[1])[0]
    
    def _assign_ucb(
        self,
        experiment: Experiment,
        c: float = 2.0,
    ) -> ExperimentVariant:
        """Upper Confidence Bound assignment."""
        total_impressions = sum(
            s.impressions for s in experiment.variant_stats.values()
        )
        
        if total_impressions == 0:
            return experiment.variants[0]
        
        best_variant = None
        best_ucb = -float('inf')
        
        for variant in experiment.variants:
            stats = experiment.variant_stats[variant.id]
            if stats.impressions == 0:
                return variant  # Try unsampled variant
            
            # UCB1 formula
            avg_reward = stats.conversion_rate
            exploration = c * math.sqrt(
                math.log(total_impressions) / stats.impressions
            )
            ucb = avg_reward + exploration
            
            if ucb > best_ucb:
                best_ucb = ucb
                best_variant = variant
        
        return best_variant
    
    # =========================================================================
    # Metrics Recording
    # =========================================================================
    
    async def record_impression(
        self,
        experiment_id: uuid.UUID,
        variant_id: str,
        user_id: str,
    ):
        """Record that a variant was shown."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return
        
        if variant_id in experiment.variant_stats:
            experiment.variant_stats[variant_id].impressions += 1
    
    async def record_conversion(
        self,
        experiment_id: uuid.UUID,
        variant_id: str,
        user_id: str,
        value: float = 1.0,
    ):
        """Record a conversion event."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return
        
        if variant_id in experiment.variant_stats:
            stats = experiment.variant_stats[variant_id]
            stats.conversions += 1
            stats.total_value += value
    
    async def record_metric(
        self,
        experiment_id: uuid.UUID,
        variant_id: str,
        metric_id: str,
        value: float,
    ):
        """Record a custom metric value."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return
        
        # Store in variant stats (simplified - real impl would track per metric)
        if variant_id in experiment.variant_stats:
            experiment.variant_stats[variant_id].total_value += value
    
    # =========================================================================
    # Statistical Analysis
    # =========================================================================
    
    async def get_experiment_stats(
        self,
        experiment_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """Get current experiment statistics."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return {}
        
        stats = {
            "experiment_id": str(experiment.id),
            "status": experiment.status.value,
            "duration_hours": self._get_duration_hours(experiment),
            "variants": {},
            "is_significant": False,
            "recommended_action": "continue",
        }
        
        for variant in experiment.variants:
            vstats = experiment.variant_stats[variant.id]
            stats["variants"][variant.id] = {
                "name": variant.name,
                "impressions": vstats.impressions,
                "conversions": vstats.conversions,
                "conversion_rate": vstats.conversion_rate,
                "mean_value": vstats.mean_value,
                "is_control": variant.is_control,
            }
        
        # Check for significance
        significance = await self._check_significance(experiment)
        stats["is_significant"] = significance["is_significant"]
        stats["confidence"] = significance.get("confidence", 0)
        stats["p_value"] = significance.get("p_value", 1.0)
        
        # Recommend action
        stats["recommended_action"] = self._get_recommendation(experiment, significance)
        
        return stats
    
    def _get_duration_hours(self, experiment: Experiment) -> float:
        """Get experiment duration in hours."""
        if not experiment.started_at:
            return 0
        
        end_time = experiment.ended_at or datetime.utcnow()
        return (end_time - experiment.started_at).total_seconds() / 3600
    
    async def _check_significance(
        self,
        experiment: Experiment,
    ) -> Dict[str, Any]:
        """Check statistical significance using chi-square test."""
        # Get control and treatment stats
        control = None
        treatment = None
        
        for variant in experiment.variants:
            if variant.is_control:
                control = experiment.variant_stats[variant.id]
            else:
                treatment = experiment.variant_stats[variant.id]
        
        if not control or not treatment:
            return {"is_significant": False}
        
        # Check minimum sample size
        total_samples = control.impressions + treatment.impressions
        if total_samples < experiment.min_sample_size:
            return {
                "is_significant": False,
                "reason": "insufficient_samples",
                "samples_needed": experiment.min_sample_size - total_samples,
            }
        
        # Chi-square test (simplified)
        # In production, use scipy.stats.chi2_contingency
        p_value = self._chi_square_test(
            control.impressions, control.conversions,
            treatment.impressions, treatment.conversions
        )
        
        confidence = 1 - p_value
        is_significant = confidence >= experiment.confidence_threshold
        
        # Calculate lift
        lift = 0
        if control.conversion_rate > 0:
            lift = (treatment.conversion_rate - control.conversion_rate) / control.conversion_rate
        
        return {
            "is_significant": is_significant,
            "confidence": confidence,
            "p_value": p_value,
            "lift": lift,
            "control_rate": control.conversion_rate,
            "treatment_rate": treatment.conversion_rate,
        }
    
    def _chi_square_test(
        self,
        n1: int, c1: int,
        n2: int, c2: int,
    ) -> float:
        """Simplified chi-square test."""
        # Create contingency table
        # [conversions, non-conversions] for each group
        if n1 == 0 or n2 == 0:
            return 1.0
        
        # Expected values under null hypothesis
        total = n1 + n2
        total_conv = c1 + c2
        total_non = total - total_conv
        
        if total_conv == 0 or total_non == 0:
            return 1.0
        
        e1c = n1 * total_conv / total
        e1n = n1 * total_non / total
        e2c = n2 * total_conv / total
        e2n = n2 * total_non / total
        
        # Chi-square statistic
        chi2 = 0
        for obs, exp in [(c1, e1c), (n1 - c1, e1n), (c2, e2c), (n2 - c2, e2n)]:
            if exp > 0:
                chi2 += (obs - exp) ** 2 / exp
        
        # Approximate p-value (1 df)
        # Using simplified approximation
        if chi2 < 3.84:
            return 0.5  # Not significant
        elif chi2 < 6.63:
            return 0.05
        elif chi2 < 10.83:
            return 0.01
        else:
            return 0.001
    
    def _get_recommendation(
        self,
        experiment: Experiment,
        significance: Dict[str, Any],
    ) -> str:
        """Get recommendation based on analysis."""
        duration_hours = self._get_duration_hours(experiment)
        max_hours = experiment.max_duration_days * 24
        
        if significance.get("is_significant"):
            lift = significance.get("lift", 0)
            if lift > 0:
                return "promote_winner"
            else:
                return "keep_control"
        
        if significance.get("reason") == "insufficient_samples":
            return "continue"
        
        if duration_hours >= max_hours:
            return "inconclusive_stop"
        
        return "continue"
    
    async def _compute_results(self, experiment: Experiment) -> ExperimentResult:
        """Compute final experiment results."""
        significance = await self._check_significance(experiment)
        
        winner_id = None
        if significance.get("is_significant"):
            # Find best performing variant
            best_rate = 0
            for variant in experiment.variants:
                stats = experiment.variant_stats[variant.id]
                if stats.conversion_rate > best_rate:
                    best_rate = stats.conversion_rate
                    winner_id = variant.id
        
        # Build metrics summary
        metrics = {}
        for variant in experiment.variants:
            stats = experiment.variant_stats[variant.id]
            metrics[variant.id] = {
                "conversion_rate": stats.conversion_rate,
                "mean_value": stats.mean_value,
                "impressions": stats.impressions,
            }
        
        recommendation = self._get_recommendation(experiment, significance)
        
        return ExperimentResult(
            experiment_id=experiment.id,
            winner_variant_id=winner_id,
            confidence=significance.get("confidence", 0),
            lift=significance.get("lift", 0) * 100,
            is_significant=significance.get("is_significant", False),
            metrics=metrics,
            recommendation=recommendation,
        )
    
    # =========================================================================
    # Auto-Promotion
    # =========================================================================
    
    async def check_and_promote(self, experiment_id: uuid.UUID) -> bool:
        """Check if experiment should be promoted and do so if configured."""
        experiment = self._experiments.get(experiment_id)
        if not experiment or not experiment.auto_promote:
            return False
        
        stats = await self.get_experiment_stats(experiment_id)
        
        if stats.get("recommended_action") == "promote_winner":
            # Find winner
            significance = await self._check_significance(experiment)
            if significance.get("is_significant") and significance.get("lift", 0) > 0:
                # Get winning variant
                for variant in experiment.variants:
                    if not variant.is_control:
                        # Promote winning prompt version
                        await self._promote_variant(experiment, variant)
                        await self.stop_experiment(experiment_id)
                        return True
        
        return False
    
    async def _promote_variant(
        self,
        experiment: Experiment,
        variant: ExperimentVariant,
    ):
        """Promote winning variant to be the default."""
        logger.info(
            "Promoting winning variant",
            experiment_id=str(experiment.id),
            variant_id=variant.id,
            prompt_id=str(variant.prompt_id),
        )
        
        # In production, this would update the prompt's "deployed" version
        # or trigger a deployment workflow


# Factory function
def get_ab_testing_service(db: AsyncSession) -> ABTestingService:
    """Create an ABTestingService instance."""
    return ABTestingService(db)
