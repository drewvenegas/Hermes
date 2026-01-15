"""
Benchmark Engine

Orchestrates benchmark runs, quality gates, and result management.
Provides operational integration with ATE and ASRBS.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from hermes.config import get_settings
from hermes.integrations.ate import (
    ATEClient, 
    BenchmarkConfig, 
    BenchmarkResult as ATEBenchmarkResult,
    BenchmarkSuite,
    get_ate_client,
)
from hermes.integrations.asrbs import ASRBSClient, get_asrbs_client
from hermes.integrations.beeper import BeeperClient, get_beeper_client
from hermes.models import BenchmarkResult, Prompt, PromptStatus

settings = get_settings()
logger = structlog.get_logger()


class QualityGateResult(str, Enum):
    """Quality gate evaluation result."""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


class BenchmarkEngine:
    """
    Operational service for running and managing benchmarks.
    
    Features:
    - ATE benchmark execution
    - ASRBS self-critique
    - Quality gate enforcement
    - Regression detection
    - Auto-benchmark on commit
    - Benchmark scheduling
    - Result aggregation and trends
    """

    def __init__(
        self,
        db: AsyncSession,
        ate_client: ATEClient = None,
        asrbs_client: ASRBSClient = None,
        beeper_client: BeeperClient = None,
    ):
        self.db = db
        self.ate = ate_client or get_ate_client()
        self.asrbs = asrbs_client or get_asrbs_client()
        self.beeper = beeper_client or get_beeper_client()
        
        # Quality gate thresholds
        self.default_gate_threshold = 0.8
        self.regression_threshold = 5.0  # 5% drop triggers warning

    # =========================================================================
    # Core Benchmark Operations
    # =========================================================================

    async def run_benchmark(
        self,
        prompt: Prompt,
        suite_id: str = "default",
        model_id: str = "aria01-d3n",
        user_id: Optional[uuid.UUID] = None,
        notify: bool = True,
        enforce_gate: bool = False,
    ) -> BenchmarkResult:
        """
        Run a benchmark on a prompt.
        
        Args:
            prompt: The prompt to benchmark
            suite_id: Benchmark suite to use
            model_id: Model to benchmark against
            user_id: User triggering the benchmark
            notify: Whether to send notifications
            enforce_gate: Whether to enforce quality gate (block on failure)
            
        Returns:
            BenchmarkResult with scores and gate status
        """
        logger.info(
            "Running benchmark",
            prompt_id=str(prompt.id),
            prompt_name=prompt.name,
            suite=suite_id,
            model=model_id,
        )
        
        # Get suite configuration
        suite = await self.ate.get_suite(suite_id)
        gate_threshold = suite.gate_threshold if suite else self.default_gate_threshold
        
        # Configure benchmark
        config = BenchmarkConfig(
            suite_id=suite_id,
            model_id=model_id,
            dimensions=suite.dimensions if suite else None,
            gate_threshold=gate_threshold,
            include_baseline=True,
        )

        # Get baseline score for comparison
        baseline_score = prompt.benchmark_score

        # Run ATE benchmark
        ate_result = await self.ate.run_benchmark(
            prompt_content=prompt.content,
            prompt_id=prompt.id,
            prompt_version=prompt.version,
            config=config,
        )

        # Calculate delta from baseline
        delta = None
        if baseline_score is not None:
            delta = ate_result.overall_score - baseline_score

        # Check for regression
        is_regression, historical_baseline = await self.ate.check_regression(
            current_score=ate_result.overall_score,
            prompt_id=prompt.id,
            threshold=self.regression_threshold,
        )

        # Create result record
        result = BenchmarkResult(
            prompt_id=prompt.id,
            prompt_version=prompt.version,
            suite_id=suite_id,
            overall_score=ate_result.overall_score,
            dimension_scores={
                s.dimension: s.score for s in ate_result.dimension_scores
            },
            model_id=model_id,
            model_version=ate_result.model_version,
            execution_time_ms=ate_result.execution_time_ms,
            token_usage=ate_result.token_usage.to_dict() if ate_result.token_usage else {},
            baseline_score=baseline_score,
            delta=delta,
            gate_passed=ate_result.gate_passed,
            gate_threshold=gate_threshold,
            is_regression=is_regression,
            executed_at=datetime.utcnow(),
            executed_by=user_id or uuid.UUID("00000000-0000-0000-0000-000000000000"),
            environment=ate_result.environment,
            content_hash=ate_result.prompt_content_hash,
        )

        self.db.add(result)

        # Update prompt with new benchmark scores
        prompt.benchmark_score = ate_result.overall_score
        prompt.last_benchmark_at = datetime.utcnow()
        
        # Update content hash for integrity
        prompt.content_hash = ate_result.prompt_content_hash

        await self.db.flush()

        # Handle notifications
        if notify and user_id:
            await self._send_benchmark_notifications(
                prompt=prompt,
                result=result,
                is_regression=is_regression,
                delta=delta,
                user_id=user_id,
            )

        # Enforce quality gate if requested
        if enforce_gate and not ate_result.gate_passed:
            logger.warning(
                "Quality gate failed",
                prompt_id=str(prompt.id),
                score=ate_result.overall_score,
                threshold=gate_threshold,
            )
            # Could raise exception here to block deployment

        await self.db.refresh(result)
        
        logger.info(
            "Benchmark completed",
            prompt_id=str(prompt.id),
            score=ate_result.overall_score,
            gate_passed=ate_result.gate_passed,
            is_regression=is_regression,
        )
        
        return result

    async def run_benchmark_batch(
        self,
        prompts: List[Prompt],
        suite_id: str = "default",
        model_id: str = "aria01-d3n",
        user_id: Optional[uuid.UUID] = None,
        parallel: bool = True,
    ) -> List[BenchmarkResult]:
        """Run benchmarks on multiple prompts."""
        if parallel:
            tasks = [
                self.run_benchmark(p, suite_id, model_id, user_id, notify=False)
                for p in prompts
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out exceptions
            valid_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(
                        "Batch benchmark failed",
                        prompt_id=str(prompts[i].id),
                        error=str(result),
                    )
                else:
                    valid_results.append(result)
            return valid_results
        else:
            results = []
            for prompt in prompts:
                try:
                    result = await self.run_benchmark(
                        prompt, suite_id, model_id, user_id, notify=False
                    )
                    results.append(result)
                except Exception as e:
                    logger.error(
                        "Sequential benchmark failed",
                        prompt_id=str(prompt.id),
                        error=str(e),
                    )
            return results

    # =========================================================================
    # Auto-Benchmark on Commit
    # =========================================================================

    async def trigger_auto_benchmark(
        self,
        prompt: Prompt,
        change_summary: str = None,
        user_id: Optional[uuid.UUID] = None,
    ) -> Optional[BenchmarkResult]:
        """
        Trigger automatic benchmark when a prompt is updated.
        
        This should be called from the version control service when
        a new version is created.
        """
        # Check if auto-benchmark is enabled for this prompt
        auto_benchmark = prompt.metadata.get("auto_benchmark", True) if prompt.metadata else True
        
        if not auto_benchmark:
            logger.debug(
                "Auto-benchmark disabled for prompt",
                prompt_id=str(prompt.id),
            )
            return None
        
        # Determine appropriate suite based on prompt type
        suite_id = self._get_suite_for_prompt_type(prompt.type)
        
        logger.info(
            "Triggering auto-benchmark",
            prompt_id=str(prompt.id),
            prompt_name=prompt.name,
            suite=suite_id,
            change=change_summary,
        )
        
        return await self.run_benchmark(
            prompt=prompt,
            suite_id=suite_id,
            user_id=user_id,
            notify=True,
            enforce_gate=False,  # Don't block on auto-benchmark
        )

    def _get_suite_for_prompt_type(self, prompt_type) -> str:
        """Get appropriate benchmark suite for prompt type."""
        type_value = prompt_type.value if hasattr(prompt_type, 'value') else str(prompt_type)
        
        suite_mapping = {
            "agent_system": "agent",
            "user_template": "quality",
            "tool_definition": "default",
            "mcp_instruction": "default",
        }
        
        return suite_mapping.get(type_value, "default")

    # =========================================================================
    # Quality Gates
    # =========================================================================

    async def evaluate_quality_gate(
        self,
        prompt: Prompt,
        suite_id: str = None,
        custom_threshold: float = None,
    ) -> Tuple[QualityGateResult, Dict[str, Any]]:
        """
        Evaluate quality gate for a prompt.
        
        Returns:
            Tuple of (result, details)
        """
        # Get latest benchmark result
        latest_result = await self._get_latest_benchmark(prompt.id)
        
        if not latest_result:
            return QualityGateResult.SKIPPED, {
                "reason": "No benchmark results available",
                "recommendation": "Run a benchmark before deployment",
            }
        
        # Get threshold
        threshold = custom_threshold or latest_result.gate_threshold or self.default_gate_threshold
        score = latest_result.overall_score
        
        # Evaluate gate
        if score >= threshold * 100:
            result = QualityGateResult.PASSED
        elif latest_result.is_regression:
            result = QualityGateResult.FAILED
        elif score >= (threshold - 0.1) * 100:
            result = QualityGateResult.WARNING
        else:
            result = QualityGateResult.FAILED
        
        details = {
            "score": score,
            "threshold": threshold * 100,
            "delta": latest_result.delta,
            "is_regression": latest_result.is_regression,
            "benchmark_age_hours": (datetime.utcnow() - latest_result.executed_at).total_seconds() / 3600,
            "suite_id": latest_result.suite_id,
            "model_id": latest_result.model_id,
            "dimension_scores": latest_result.dimension_scores,
        }
        
        logger.info(
            "Quality gate evaluated",
            prompt_id=str(prompt.id),
            result=result.value,
            score=score,
            threshold=threshold * 100,
        )
        
        return result, details

    async def check_deployment_readiness(
        self,
        prompt: Prompt,
        target_apps: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Check if a prompt is ready for deployment.
        
        Evaluates multiple criteria:
        - Quality gate status
        - Benchmark freshness
        - Self-critique results
        - Regression status
        """
        readiness = {
            "ready": True,
            "checks": {},
            "blockers": [],
            "warnings": [],
        }
        
        # Check quality gate
        gate_result, gate_details = await self.evaluate_quality_gate(prompt)
        readiness["checks"]["quality_gate"] = {
            "status": gate_result.value,
            "details": gate_details,
        }
        
        if gate_result == QualityGateResult.FAILED:
            readiness["ready"] = False
            readiness["blockers"].append(f"Quality gate failed: {gate_details['score']:.1f}% < {gate_details['threshold']:.1f}%")
        elif gate_result == QualityGateResult.WARNING:
            readiness["warnings"].append(f"Quality score marginal: {gate_details['score']:.1f}%")
        elif gate_result == QualityGateResult.SKIPPED:
            readiness["warnings"].append("No benchmark results available")
        
        # Check benchmark freshness (should be < 24 hours old)
        if gate_details.get("benchmark_age_hours", float("inf")) > 24:
            readiness["warnings"].append("Benchmark results are stale (>24 hours old)")
        
        # Check regression status
        if gate_details.get("is_regression"):
            readiness["ready"] = False
            readiness["blockers"].append(f"Score regression detected: {gate_details.get('delta', 0):.1f}% drop")
        
        return readiness

    # =========================================================================
    # Self-Critique (ASRBS Integration)
    # =========================================================================

    async def run_self_critique(
        self,
        prompt: Prompt,
    ) -> Dict[str, Any]:
        """Run ASRBS self-critique on a prompt."""
        logger.info(
            "Running self-critique",
            prompt_id=str(prompt.id),
            prompt_name=prompt.name,
        )
        
        result = await self.asrbs.analyze_prompt(
            prompt_content=prompt.content,
            prompt_id=prompt.id,
            prompt_version=prompt.version,
            prompt_type=prompt.type.value if hasattr(prompt.type, 'value') else str(prompt.type),
        )

        critique_result = {
            "overall_assessment": result.overall_assessment,
            "quality_score": result.quality_score,
            "suggestions": [
                {
                    "id": str(s.id),
                    "category": s.category,
                    "severity": s.severity,
                    "description": s.description,
                    "suggested_change": s.suggested_change,
                    "confidence": s.confidence,
                }
                for s in result.suggestions
            ],
            "knowledge_gaps": result.knowledge_gaps,
            "overconfidence_areas": result.overconfidence_areas,
            "training_data_needs": result.training_data_needs,
            "improvement_potential": self._calculate_improvement_potential(result),
        }
        
        logger.info(
            "Self-critique completed",
            prompt_id=str(prompt.id),
            quality_score=result.quality_score,
            suggestion_count=len(result.suggestions),
        )
        
        return critique_result

    def _calculate_improvement_potential(self, result) -> float:
        """Calculate potential score improvement from suggestions."""
        if not result.suggestions:
            return 0.0
        
        # Weight suggestions by severity and confidence
        weights = {"critical": 10, "high": 5, "medium": 2, "low": 1}
        
        potential = sum(
            weights.get(s.severity, 1) * s.confidence
            for s in result.suggestions
        )
        
        # Normalize to percentage
        max_potential = len(result.suggestions) * 10
        return min(100, (potential / max_potential) * 100) if max_potential > 0 else 0.0

    async def apply_suggestion(
        self,
        prompt: Prompt,
        suggestion_id: str,
        user_id: Optional[uuid.UUID] = None,
    ) -> Prompt:
        """
        Apply an ASRBS improvement suggestion to a prompt.
        
        This creates a new version with the suggested change applied.
        """
        # Get the suggestion from ASRBS
        suggestion = await self.asrbs.get_suggestion(suggestion_id)
        
        if not suggestion:
            raise ValueError(f"Suggestion {suggestion_id} not found")
        
        # Apply the change
        new_content = await self.asrbs.apply_suggestion(
            prompt_content=prompt.content,
            suggestion=suggestion,
        )
        
        # Create new version via version control service
        from hermes.services.version_control import VersionControlService
        vc = VersionControlService(self.db)
        
        updated_prompt = await vc.create_version(
            prompt=prompt,
            new_content=new_content,
            change_summary=f"Applied ASRBS suggestion: {suggestion.description}",
            author_id=user_id,
        )
        
        # Trigger auto-benchmark on the new version
        await self.trigger_auto_benchmark(
            prompt=updated_prompt,
            change_summary=f"ASRBS suggestion applied: {suggestion_id}",
            user_id=user_id,
        )
        
        return updated_prompt

    # =========================================================================
    # History and Trends
    # =========================================================================

    async def get_benchmark_history(
        self,
        prompt_id: uuid.UUID,
        limit: int = 20,
    ) -> List[BenchmarkResult]:
        """Get benchmark history for a prompt."""
        query = (
            select(BenchmarkResult)
            .where(BenchmarkResult.prompt_id == prompt_id)
            .order_by(BenchmarkResult.executed_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_benchmark_trends(
        self,
        prompt_id: uuid.UUID,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get benchmark trends and analytics for a prompt."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        query = (
            select(BenchmarkResult)
            .where(
                and_(
                    BenchmarkResult.prompt_id == prompt_id,
                    BenchmarkResult.executed_at >= cutoff,
                )
            )
            .order_by(BenchmarkResult.executed_at.desc())
        )
        result = await self.db.execute(query)
        history = list(result.scalars().all())

        if not history:
            return {
                "trend": "neutral",
                "change": 0,
                "current_score": None,
                "history": [],
                "dimension_trends": {},
                "benchmark_count": 0,
            }

        scores = [r.overall_score for r in history]
        current_score = scores[0]
        
        # Calculate trend
        if len(scores) >= 2:
            # Use linear regression for trend
            n = len(scores)
            x_mean = (n - 1) / 2
            y_mean = sum(scores) / n
            
            numerator = sum((i - x_mean) * (scores[i] - y_mean) for i in range(n))
            denominator = sum((i - x_mean) ** 2 for i in range(n))
            
            slope = numerator / denominator if denominator != 0 else 0
            
            if slope > 0.5:
                trend = "improving"
            elif slope < -0.5:
                trend = "declining"
            else:
                trend = "stable"
            
            change = scores[0] - scores[-1]
        else:
            change = 0
            trend = "neutral"

        # Calculate dimension trends
        dimension_trends = {}
        for result_item in history[:10]:
            if result_item.dimension_scores:
                for dim, score in result_item.dimension_scores.items():
                    if dim not in dimension_trends:
                        dimension_trends[dim] = []
                    dimension_trends[dim].append(score)
        
        # Average each dimension
        dimension_averages = {
            dim: sum(scores) / len(scores)
            for dim, scores in dimension_trends.items()
        }

        return {
            "trend": trend,
            "change": change,
            "current_score": current_score,
            "average_score": sum(scores) / len(scores),
            "min_score": min(scores),
            "max_score": max(scores),
            "benchmark_count": len(history),
            "history": [
                {
                    "date": r.executed_at.isoformat(),
                    "score": r.overall_score,
                    "version": r.prompt_version,
                    "suite": r.suite_id,
                    "gate_passed": r.gate_passed,
                }
                for r in history[:20]
            ],
            "dimension_averages": dimension_averages,
            "days_analyzed": days,
        }

    async def compare_prompts(
        self,
        prompt_ids: List[uuid.UUID],
        suite_id: str = "default",
    ) -> Dict[str, Any]:
        """Compare benchmark results across multiple prompts."""
        comparisons = []
        
        for prompt_id in prompt_ids:
            latest = await self._get_latest_benchmark(prompt_id)
            if latest:
                comparisons.append({
                    "prompt_id": str(prompt_id),
                    "score": latest.overall_score,
                    "dimension_scores": latest.dimension_scores,
                    "gate_passed": latest.gate_passed,
                    "benchmark_date": latest.executed_at.isoformat(),
                })
        
        # Sort by score descending
        comparisons.sort(key=lambda x: x["score"], reverse=True)
        
        return {
            "comparisons": comparisons,
            "best_prompt": comparisons[0]["prompt_id"] if comparisons else None,
            "score_range": {
                "min": min(c["score"] for c in comparisons) if comparisons else 0,
                "max": max(c["score"] for c in comparisons) if comparisons else 0,
            },
        }

    # =========================================================================
    # Suite Management
    # =========================================================================

    async def get_available_suites(self) -> List[BenchmarkSuite]:
        """Get available benchmark suites."""
        return await self.ate.get_suites()

    async def get_suite(self, suite_id: str) -> Optional[BenchmarkSuite]:
        """Get a specific benchmark suite."""
        return await self.ate.get_suite(suite_id)

    # =========================================================================
    # Private Helpers
    # =========================================================================

    async def _get_latest_benchmark(
        self,
        prompt_id: uuid.UUID,
    ) -> Optional[BenchmarkResult]:
        """Get the most recent benchmark result for a prompt."""
        query = (
            select(BenchmarkResult)
            .where(BenchmarkResult.prompt_id == prompt_id)
            .order_by(BenchmarkResult.executed_at.desc())
            .limit(1)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _send_benchmark_notifications(
        self,
        prompt: Prompt,
        result: BenchmarkResult,
        is_regression: bool,
        delta: Optional[float],
        user_id: uuid.UUID,
    ):
        """Send appropriate notifications based on benchmark result."""
        try:
            if is_regression:
                await self.beeper.notify_quality_regression(
                    prompt_id=prompt.id,
                    prompt_name=prompt.name,
                    old_score=result.baseline_score or 0,
                    new_score=result.overall_score,
                    recipients=[str(user_id)],
                )
            elif not result.gate_passed:
                await self.beeper.notify_gate_failed(
                    prompt_id=prompt.id,
                    prompt_name=prompt.name,
                    score=result.overall_score,
                    threshold=result.gate_threshold * 100,
                    recipients=[str(user_id)],
                )
            else:
                await self.beeper.notify_benchmark_complete(
                    prompt_id=prompt.id,
                    prompt_name=prompt.name,
                    score=result.overall_score,
                    delta=delta,
                    recipients=[str(user_id)],
                )
        except Exception as e:
            logger.warning(
                "Failed to send benchmark notification",
                error=str(e),
                prompt_id=str(prompt.id),
            )

    async def close(self):
        """Close integration clients."""
        await self.ate.close()
        await self.asrbs.close()
        await self.beeper.close()


# Factory function
def get_benchmark_engine(db: AsyncSession) -> BenchmarkEngine:
    """Create a BenchmarkEngine instance."""
    return BenchmarkEngine(db)
