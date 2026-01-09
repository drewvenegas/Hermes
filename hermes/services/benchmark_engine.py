"""
Benchmark Engine

Orchestrates benchmark runs and manages results.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hermes.config import get_settings
from hermes.integrations.ate import ATEClient, BenchmarkConfig
from hermes.integrations.asrbs import ASRBSClient
from hermes.integrations.beeper import BeeperClient
from hermes.models import BenchmarkResult, Prompt

settings = get_settings()


class BenchmarkEngine:
    """Service for running and managing benchmarks."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.ate = ATEClient()
        self.asrbs = ASRBSClient()
        self.beeper = BeeperClient()

    async def run_benchmark(
        self,
        prompt: Prompt,
        suite_id: str = "default",
        model_id: str = "aria01-d3n",
        user_id: Optional[uuid.UUID] = None,
        notify: bool = True,
    ) -> BenchmarkResult:
        """Run a benchmark on a prompt."""
        # Configure benchmark
        config = BenchmarkConfig(
            suite_id=suite_id,
            model_id=model_id,
        )

        # Get previous score for comparison
        baseline_score = prompt.benchmark_score

        # Run ATE benchmark
        ate_result = await self.ate.run_benchmark(
            prompt_content=prompt.content,
            prompt_id=prompt.id,
            prompt_version=prompt.version,
            config=config,
        )

        # Calculate delta
        delta = None
        if baseline_score is not None:
            delta = ate_result.overall_score - baseline_score

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
            token_usage=ate_result.token_usage,
            baseline_score=baseline_score,
            delta=delta,
            gate_passed=ate_result.gate_passed,
            executed_at=datetime.utcnow(),
            executed_by=user_id or uuid.UUID("00000000-0000-0000-0000-000000000000"),
            environment="staging",
        )

        self.db.add(result)

        # Update prompt scores
        prompt.benchmark_score = ate_result.overall_score
        prompt.last_benchmark_at = datetime.utcnow()

        await self.db.flush()

        # Send notifications
        if notify and user_id:
            # Check for regression
            if delta and delta < -5:
                await self.beeper.notify_quality_regression(
                    prompt_id=prompt.id,
                    prompt_name=prompt.name,
                    old_score=baseline_score or 0,
                    new_score=ate_result.overall_score,
                    recipients=[str(user_id)],
                )
            else:
                await self.beeper.notify_benchmark_complete(
                    prompt_id=prompt.id,
                    prompt_name=prompt.name,
                    score=ate_result.overall_score,
                    delta=delta,
                    recipients=[str(user_id)],
                )

        await self.db.refresh(result)
        return result

    async def run_self_critique(
        self,
        prompt: Prompt,
    ) -> dict:
        """Run ASRBS self-critique on a prompt."""
        result = await self.asrbs.analyze_prompt(
            prompt_content=prompt.content,
            prompt_id=prompt.id,
            prompt_version=prompt.version,
            prompt_type=prompt.type.value,
        )

        return {
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
        }

    async def get_benchmark_history(
        self,
        prompt_id: uuid.UUID,
        limit: int = 20,
    ) -> list[BenchmarkResult]:
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
    ) -> dict:
        """Get benchmark trends for a prompt."""
        history = await self.get_benchmark_history(prompt_id, limit=100)

        if not history:
            return {"trend": "neutral", "change": 0, "history": []}

        # Calculate trend
        scores = [r.overall_score for r in history]
        if len(scores) >= 2:
            change = scores[0] - scores[-1]
            trend = "improving" if change > 0 else "declining" if change < 0 else "stable"
        else:
            change = 0
            trend = "neutral"

        return {
            "trend": trend,
            "change": change,
            "current_score": scores[0] if scores else None,
            "history": [
                {
                    "date": r.executed_at.isoformat(),
                    "score": r.overall_score,
                    "version": r.prompt_version,
                }
                for r in history[:10]
            ],
        }

    async def close(self):
        """Close integration clients."""
        await self.ate.close()
        await self.asrbs.close()
        await self.beeper.close()
