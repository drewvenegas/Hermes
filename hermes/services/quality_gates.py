"""
Quality Gates Service

Enforces quality standards for prompt deployment.
Provides configurable gates with multi-dimensional evaluation.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from hermes.config import get_settings
from hermes.models import BenchmarkResult, Prompt, PromptStatus
from hermes.services.benchmark_engine import BenchmarkEngine

settings = get_settings()
logger = structlog.get_logger()


class GateStatus(str, Enum):
    """Quality gate evaluation status."""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"
    PENDING = "pending"


class GateType(str, Enum):
    """Types of quality gates."""
    SCORE_THRESHOLD = "score_threshold"
    REGRESSION_CHECK = "regression_check"
    BENCHMARK_FRESHNESS = "benchmark_freshness"
    DIMENSION_MINIMUM = "dimension_minimum"
    CUSTOM = "custom"


@dataclass
class GateConfig:
    """Configuration for a quality gate."""
    id: str
    name: str
    gate_type: GateType
    enabled: bool = True
    blocking: bool = True  # If True, gate failure blocks deployment
    threshold: float = 0.8
    dimension: Optional[str] = None  # For dimension-specific gates
    max_age_hours: int = 24  # For freshness gates
    regression_threshold: float = 5.0  # Percentage drop that triggers regression
    custom_evaluator: Optional[str] = None  # For custom gates
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GateEvaluation:
    """Result of evaluating a single gate."""
    gate_id: str
    gate_name: str
    gate_type: GateType
    status: GateStatus
    blocking: bool
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    evaluated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class GateReport:
    """Complete quality gate evaluation report."""
    prompt_id: uuid.UUID
    prompt_version: str
    overall_status: GateStatus
    can_deploy: bool
    evaluations: List[GateEvaluation]
    summary: str
    evaluated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt_id": str(self.prompt_id),
            "prompt_version": self.prompt_version,
            "overall_status": self.overall_status.value,
            "can_deploy": self.can_deploy,
            "evaluations": [
                {
                    "gate_id": e.gate_id,
                    "gate_name": e.gate_name,
                    "gate_type": e.gate_type.value,
                    "status": e.status.value,
                    "blocking": e.blocking,
                    "message": e.message,
                    "details": e.details,
                }
                for e in self.evaluations
            ],
            "summary": self.summary,
            "evaluated_at": self.evaluated_at.isoformat(),
            "metadata": self.metadata,
        }


# Default quality gates configuration
DEFAULT_GATES = [
    GateConfig(
        id="score-minimum",
        name="Minimum Score Threshold",
        gate_type=GateType.SCORE_THRESHOLD,
        enabled=True,
        blocking=True,
        threshold=0.8,
    ),
    GateConfig(
        id="regression-check",
        name="Regression Detection",
        gate_type=GateType.REGRESSION_CHECK,
        enabled=True,
        blocking=True,
        regression_threshold=5.0,
    ),
    GateConfig(
        id="benchmark-freshness",
        name="Benchmark Freshness",
        gate_type=GateType.BENCHMARK_FRESHNESS,
        enabled=True,
        blocking=False,  # Warning only
        max_age_hours=24,
    ),
    GateConfig(
        id="safety-minimum",
        name="Safety Dimension Minimum",
        gate_type=GateType.DIMENSION_MINIMUM,
        enabled=True,
        blocking=True,
        threshold=0.85,
        dimension="safety",
    ),
]


class QualityGateService:
    """
    Service for evaluating and enforcing quality gates.
    
    Features:
    - Configurable gate policies
    - Multi-dimensional evaluation
    - Regression detection
    - Benchmark freshness checks
    - Custom gate support
    - Deployment blocking
    """

    def __init__(
        self,
        db: AsyncSession,
        gates: List[GateConfig] = None,
    ):
        self.db = db
        self.gates = gates or DEFAULT_GATES
        self._gate_map = {g.id: g for g in self.gates}

    # =========================================================================
    # Gate Evaluation
    # =========================================================================

    async def evaluate_gates(
        self,
        prompt: Prompt,
        target_environment: str = "production",
        custom_gates: List[GateConfig] = None,
    ) -> GateReport:
        """
        Evaluate all quality gates for a prompt.
        
        Args:
            prompt: The prompt to evaluate
            target_environment: Deployment target (affects strictness)
            custom_gates: Additional gates to evaluate
            
        Returns:
            GateReport with all evaluation results
        """
        logger.info(
            "Evaluating quality gates",
            prompt_id=str(prompt.id),
            prompt_name=prompt.name,
            environment=target_environment,
        )
        
        # Combine default and custom gates
        gates_to_evaluate = list(self.gates)
        if custom_gates:
            gates_to_evaluate.extend(custom_gates)
        
        # Get latest benchmark result
        latest_benchmark = await self._get_latest_benchmark(prompt.id)
        
        # Evaluate each gate
        evaluations: List[GateEvaluation] = []
        for gate in gates_to_evaluate:
            if not gate.enabled:
                continue
            
            evaluation = await self._evaluate_gate(
                gate, prompt, latest_benchmark, target_environment
            )
            evaluations.append(evaluation)
        
        # Determine overall status
        overall_status, can_deploy = self._determine_overall_status(evaluations)
        
        # Generate summary
        summary = self._generate_summary(evaluations, overall_status)
        
        report = GateReport(
            prompt_id=prompt.id,
            prompt_version=prompt.version,
            overall_status=overall_status,
            can_deploy=can_deploy,
            evaluations=evaluations,
            summary=summary,
            metadata={
                "environment": target_environment,
                "gates_evaluated": len(evaluations),
                "gates_passed": sum(1 for e in evaluations if e.status == GateStatus.PASSED),
                "gates_failed": sum(1 for e in evaluations if e.status == GateStatus.FAILED),
            },
        )
        
        logger.info(
            "Quality gate evaluation complete",
            prompt_id=str(prompt.id),
            status=overall_status.value,
            can_deploy=can_deploy,
        )
        
        return report

    async def _evaluate_gate(
        self,
        gate: GateConfig,
        prompt: Prompt,
        benchmark: Optional[BenchmarkResult],
        environment: str,
    ) -> GateEvaluation:
        """Evaluate a single gate."""
        
        if gate.gate_type == GateType.SCORE_THRESHOLD:
            return await self._evaluate_score_threshold(gate, benchmark)
        
        elif gate.gate_type == GateType.REGRESSION_CHECK:
            return await self._evaluate_regression(gate, prompt, benchmark)
        
        elif gate.gate_type == GateType.BENCHMARK_FRESHNESS:
            return await self._evaluate_freshness(gate, benchmark)
        
        elif gate.gate_type == GateType.DIMENSION_MINIMUM:
            return await self._evaluate_dimension(gate, benchmark)
        
        elif gate.gate_type == GateType.CUSTOM:
            return await self._evaluate_custom(gate, prompt, benchmark, environment)
        
        else:
            return GateEvaluation(
                gate_id=gate.id,
                gate_name=gate.name,
                gate_type=gate.gate_type,
                status=GateStatus.SKIPPED,
                blocking=gate.blocking,
                message=f"Unknown gate type: {gate.gate_type}",
            )

    async def _evaluate_score_threshold(
        self,
        gate: GateConfig,
        benchmark: Optional[BenchmarkResult],
    ) -> GateEvaluation:
        """Evaluate minimum score threshold gate."""
        if not benchmark:
            return GateEvaluation(
                gate_id=gate.id,
                gate_name=gate.name,
                gate_type=gate.gate_type,
                status=GateStatus.PENDING,
                blocking=gate.blocking,
                message="No benchmark results available",
                details={"recommendation": "Run a benchmark before deployment"},
            )
        
        threshold_pct = gate.threshold * 100
        
        if benchmark.overall_score >= threshold_pct:
            return GateEvaluation(
                gate_id=gate.id,
                gate_name=gate.name,
                gate_type=gate.gate_type,
                status=GateStatus.PASSED,
                blocking=gate.blocking,
                message=f"Score {benchmark.overall_score:.1f}% meets threshold {threshold_pct:.1f}%",
                details={
                    "score": benchmark.overall_score,
                    "threshold": threshold_pct,
                    "margin": benchmark.overall_score - threshold_pct,
                },
            )
        else:
            return GateEvaluation(
                gate_id=gate.id,
                gate_name=gate.name,
                gate_type=gate.gate_type,
                status=GateStatus.FAILED,
                blocking=gate.blocking,
                message=f"Score {benchmark.overall_score:.1f}% below threshold {threshold_pct:.1f}%",
                details={
                    "score": benchmark.overall_score,
                    "threshold": threshold_pct,
                    "gap": threshold_pct - benchmark.overall_score,
                },
            )

    async def _evaluate_regression(
        self,
        gate: GateConfig,
        prompt: Prompt,
        benchmark: Optional[BenchmarkResult],
    ) -> GateEvaluation:
        """Evaluate regression detection gate."""
        if not benchmark:
            return GateEvaluation(
                gate_id=gate.id,
                gate_name=gate.name,
                gate_type=gate.gate_type,
                status=GateStatus.SKIPPED,
                blocking=gate.blocking,
                message="No benchmark results for regression check",
            )
        
        # Check is_regression flag from benchmark
        if benchmark.is_regression:
            return GateEvaluation(
                gate_id=gate.id,
                gate_name=gate.name,
                gate_type=gate.gate_type,
                status=GateStatus.FAILED,
                blocking=gate.blocking,
                message=f"Quality regression detected: {benchmark.delta:.1f}% drop",
                details={
                    "current_score": benchmark.overall_score,
                    "baseline_score": benchmark.baseline_score,
                    "delta": benchmark.delta,
                    "threshold": gate.regression_threshold,
                },
            )
        
        # Also check delta if available
        if benchmark.delta is not None and benchmark.delta < -gate.regression_threshold:
            return GateEvaluation(
                gate_id=gate.id,
                gate_name=gate.name,
                gate_type=gate.gate_type,
                status=GateStatus.WARNING,
                blocking=False,  # Warning only for borderline cases
                message=f"Score decreased by {abs(benchmark.delta):.1f}%",
                details={
                    "delta": benchmark.delta,
                    "threshold": gate.regression_threshold,
                },
            )
        
        return GateEvaluation(
            gate_id=gate.id,
            gate_name=gate.name,
            gate_type=gate.gate_type,
            status=GateStatus.PASSED,
            blocking=gate.blocking,
            message="No regression detected",
            details={"delta": benchmark.delta or 0},
        )

    async def _evaluate_freshness(
        self,
        gate: GateConfig,
        benchmark: Optional[BenchmarkResult],
    ) -> GateEvaluation:
        """Evaluate benchmark freshness gate."""
        if not benchmark:
            return GateEvaluation(
                gate_id=gate.id,
                gate_name=gate.name,
                gate_type=gate.gate_type,
                status=GateStatus.WARNING,
                blocking=gate.blocking,
                message="No benchmark results available",
            )
        
        age = datetime.utcnow() - benchmark.executed_at
        age_hours = age.total_seconds() / 3600
        
        if age_hours <= gate.max_age_hours:
            return GateEvaluation(
                gate_id=gate.id,
                gate_name=gate.name,
                gate_type=gate.gate_type,
                status=GateStatus.PASSED,
                blocking=gate.blocking,
                message=f"Benchmark is {age_hours:.1f} hours old",
                details={
                    "age_hours": age_hours,
                    "max_age_hours": gate.max_age_hours,
                },
            )
        else:
            return GateEvaluation(
                gate_id=gate.id,
                gate_name=gate.name,
                gate_type=gate.gate_type,
                status=GateStatus.WARNING,
                blocking=gate.blocking,
                message=f"Benchmark is stale ({age_hours:.1f} hours old, max {gate.max_age_hours}h)",
                details={
                    "age_hours": age_hours,
                    "max_age_hours": gate.max_age_hours,
                    "recommendation": "Re-run benchmark before deployment",
                },
            )

    async def _evaluate_dimension(
        self,
        gate: GateConfig,
        benchmark: Optional[BenchmarkResult],
    ) -> GateEvaluation:
        """Evaluate dimension-specific minimum gate."""
        if not benchmark:
            return GateEvaluation(
                gate_id=gate.id,
                gate_name=gate.name,
                gate_type=gate.gate_type,
                status=GateStatus.PENDING,
                blocking=gate.blocking,
                message=f"No benchmark results for {gate.dimension} check",
            )
        
        if not benchmark.dimension_scores or gate.dimension not in benchmark.dimension_scores:
            return GateEvaluation(
                gate_id=gate.id,
                gate_name=gate.name,
                gate_type=gate.gate_type,
                status=GateStatus.SKIPPED,
                blocking=gate.blocking,
                message=f"Dimension '{gate.dimension}' not in benchmark results",
                details={"available_dimensions": list(benchmark.dimension_scores.keys()) if benchmark.dimension_scores else []},
            )
        
        score = benchmark.dimension_scores[gate.dimension]
        threshold_pct = gate.threshold * 100
        
        if score >= threshold_pct:
            return GateEvaluation(
                gate_id=gate.id,
                gate_name=gate.name,
                gate_type=gate.gate_type,
                status=GateStatus.PASSED,
                blocking=gate.blocking,
                message=f"{gate.dimension.title()} score {score:.1f}% meets threshold {threshold_pct:.1f}%",
                details={
                    "dimension": gate.dimension,
                    "score": score,
                    "threshold": threshold_pct,
                },
            )
        else:
            return GateEvaluation(
                gate_id=gate.id,
                gate_name=gate.name,
                gate_type=gate.gate_type,
                status=GateStatus.FAILED,
                blocking=gate.blocking,
                message=f"{gate.dimension.title()} score {score:.1f}% below threshold {threshold_pct:.1f}%",
                details={
                    "dimension": gate.dimension,
                    "score": score,
                    "threshold": threshold_pct,
                    "gap": threshold_pct - score,
                },
            )

    async def _evaluate_custom(
        self,
        gate: GateConfig,
        prompt: Prompt,
        benchmark: Optional[BenchmarkResult],
        environment: str,
    ) -> GateEvaluation:
        """Evaluate custom gate using registered evaluator."""
        # Custom gates would be implemented as plugins
        # For now, return skipped
        return GateEvaluation(
            gate_id=gate.id,
            gate_name=gate.name,
            gate_type=gate.gate_type,
            status=GateStatus.SKIPPED,
            blocking=gate.blocking,
            message=f"Custom gate '{gate.custom_evaluator}' not implemented",
        )

    def _determine_overall_status(
        self,
        evaluations: List[GateEvaluation],
    ) -> Tuple[GateStatus, bool]:
        """Determine overall gate status and deployment eligibility."""
        if not evaluations:
            return GateStatus.SKIPPED, True
        
        # Check for blocking failures
        blocking_failures = [
            e for e in evaluations
            if e.status == GateStatus.FAILED and e.blocking
        ]
        
        if blocking_failures:
            return GateStatus.FAILED, False
        
        # Check for any failures (non-blocking)
        all_failures = [e for e in evaluations if e.status == GateStatus.FAILED]
        if all_failures:
            return GateStatus.WARNING, True  # Can deploy with warnings
        
        # Check for warnings
        warnings = [e for e in evaluations if e.status == GateStatus.WARNING]
        if warnings:
            return GateStatus.WARNING, True
        
        # Check for pending
        pending = [e for e in evaluations if e.status == GateStatus.PENDING]
        if pending and len(pending) == len(evaluations):
            return GateStatus.PENDING, False  # All pending = can't deploy
        
        return GateStatus.PASSED, True

    def _generate_summary(
        self,
        evaluations: List[GateEvaluation],
        overall_status: GateStatus,
    ) -> str:
        """Generate human-readable summary."""
        total = len(evaluations)
        passed = sum(1 for e in evaluations if e.status == GateStatus.PASSED)
        failed = sum(1 for e in evaluations if e.status == GateStatus.FAILED)
        warnings = sum(1 for e in evaluations if e.status == GateStatus.WARNING)
        
        if overall_status == GateStatus.PASSED:
            return f"All {total} quality gates passed. Ready for deployment."
        elif overall_status == GateStatus.FAILED:
            blocking = [e.gate_name for e in evaluations if e.status == GateStatus.FAILED and e.blocking]
            return f"Deployment blocked: {failed} gate(s) failed. Blocking gates: {', '.join(blocking)}"
        elif overall_status == GateStatus.WARNING:
            return f"{passed} passed, {warnings} warning(s), {failed} non-blocking failure(s). Deployment allowed with caution."
        elif overall_status == GateStatus.PENDING:
            return f"Evaluation incomplete: {total - passed - failed - warnings} gate(s) pending. Run benchmarks first."
        else:
            return f"Gate evaluation skipped."

    # =========================================================================
    # Gate Management
    # =========================================================================

    def get_gate(self, gate_id: str) -> Optional[GateConfig]:
        """Get a specific gate configuration."""
        return self._gate_map.get(gate_id)

    def get_all_gates(self) -> List[GateConfig]:
        """Get all configured gates."""
        return list(self.gates)

    def add_gate(self, gate: GateConfig):
        """Add a new gate configuration."""
        self.gates.append(gate)
        self._gate_map[gate.id] = gate

    def update_gate(self, gate_id: str, **updates):
        """Update a gate configuration."""
        if gate_id in self._gate_map:
            gate = self._gate_map[gate_id]
            for key, value in updates.items():
                if hasattr(gate, key):
                    setattr(gate, key, value)

    def remove_gate(self, gate_id: str):
        """Remove a gate configuration."""
        if gate_id in self._gate_map:
            gate = self._gate_map.pop(gate_id)
            self.gates.remove(gate)

    # =========================================================================
    # Private Helpers
    # =========================================================================

    async def _get_latest_benchmark(
        self,
        prompt_id: uuid.UUID,
    ) -> Optional[BenchmarkResult]:
        """Get the most recent benchmark result."""
        query = (
            select(BenchmarkResult)
            .where(BenchmarkResult.prompt_id == prompt_id)
            .order_by(BenchmarkResult.executed_at.desc())
            .limit(1)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()


# Factory function
def get_quality_gate_service(
    db: AsyncSession,
    gates: List[GateConfig] = None,
) -> QualityGateService:
    """Create a QualityGateService instance."""
    return QualityGateService(db, gates)
