"""
Benchmark Service

Multi-model benchmark comparison and trend analysis.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hermes.config import get_settings
from hermes.models.benchmark import BenchmarkResult
from hermes.models.benchmark_suite import BenchmarkSuite, BenchmarkTestCase
from hermes.models.prompt import Prompt

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class ModelResult:
    """Result for a single model in multi-model comparison."""
    model_id: str
    model_version: Optional[str]
    overall_score: float
    dimension_scores: Dict[str, float]
    execution_time_ms: int
    token_usage: Optional[Dict[str, Any]]
    gate_passed: bool


@dataclass
class MultiModelResult:
    """Combined result of multi-model benchmark."""
    prompt_id: uuid.UUID
    prompt_version: str
    suite_id: str
    model_results: List[ModelResult]
    best_model: str
    best_score: float
    comparison_matrix: Dict[str, Dict[str, float]]
    executed_at: datetime


@dataclass
class TrendPoint:
    """A single point in benchmark trend analysis."""
    timestamp: datetime
    score: float
    version: str
    model_id: str


@dataclass
class BenchmarkTrends:
    """Benchmark trend analysis results."""
    prompt_id: uuid.UUID
    trend_data: List[TrendPoint]
    rolling_avg_7d: Optional[float]
    rolling_avg_30d: Optional[float]
    score_delta_7d: Optional[float]
    score_delta_30d: Optional[float]
    is_regressing: bool
    regression_alert: Optional[str]


class BenchmarkService:
    """Service for benchmark operations including multi-model comparison."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def run_single_model_benchmark(
        self,
        prompt: Prompt,
        model_id: str,
        suite_id: str,
        executed_by: uuid.UUID,
    ) -> ModelResult:
        """Run benchmark for a single model.
        
        In production, this calls ATE service. For now, simulates results.
        """
        import random

        # Simulate benchmark execution
        await asyncio.sleep(0.1)  # Simulate network call

        overall_score = random.uniform(70, 95)
        dimension_scores = {
            "quality": random.uniform(70, 95),
            "safety": random.uniform(80, 99),
            "performance": random.uniform(60, 90),
            "clarity": random.uniform(70, 95),
        }

        return ModelResult(
            model_id=model_id,
            model_version="1.0.0",
            overall_score=overall_score,
            dimension_scores=dimension_scores,
            execution_time_ms=random.randint(100, 500),
            token_usage={"input": random.randint(100, 500), "output": random.randint(200, 1000)},
            gate_passed=overall_score >= 80,
        )

    async def run_multi_model_benchmark(
        self,
        prompt_id: uuid.UUID,
        model_ids: List[str],
        suite_id: str,
        executed_by: uuid.UUID,
        parallel: bool = True,
    ) -> MultiModelResult:
        """Run benchmark against multiple models and compare results."""
        # Get prompt
        query = select(Prompt).where(Prompt.id == prompt_id)
        result = await self.db.execute(query)
        prompt = result.scalar_one_or_none()
        
        if not prompt:
            raise ValueError(f"Prompt {prompt_id} not found")

        # Run benchmarks
        if parallel:
            tasks = [
                self.run_single_model_benchmark(prompt, model_id, suite_id, executed_by)
                for model_id in model_ids
            ]
            model_results = await asyncio.gather(*tasks)
        else:
            model_results = []
            for model_id in model_ids:
                result = await self.run_single_model_benchmark(
                    prompt, model_id, suite_id, executed_by
                )
                model_results.append(result)

        # Find best model
        best_result = max(model_results, key=lambda r: r.overall_score)

        # Build comparison matrix
        comparison_matrix = {}
        for result in model_results:
            comparison_matrix[result.model_id] = result.dimension_scores

        # Store individual results
        for model_result in model_results:
            benchmark = BenchmarkResult(
                prompt_id=prompt_id,
                prompt_version=prompt.version,
                suite_id=suite_id,
                overall_score=model_result.overall_score,
                dimension_scores=model_result.dimension_scores,
                model_id=model_result.model_id,
                model_version=model_result.model_version,
                execution_time_ms=model_result.execution_time_ms,
                token_usage=model_result.token_usage,
                baseline_score=prompt.benchmark_score,
                delta=(model_result.overall_score - prompt.benchmark_score) if prompt.benchmark_score else None,
                gate_passed=model_result.gate_passed,
                executed_at=datetime.utcnow(),
                executed_by=executed_by,
                environment="staging",
            )
            self.db.add(benchmark)

        # Update prompt with best score
        prompt.benchmark_score = best_result.overall_score
        prompt.last_benchmark_at = datetime.utcnow()
        
        await self.db.flush()

        return MultiModelResult(
            prompt_id=prompt_id,
            prompt_version=prompt.version,
            suite_id=suite_id,
            model_results=model_results,
            best_model=best_result.model_id,
            best_score=best_result.overall_score,
            comparison_matrix=comparison_matrix,
            executed_at=datetime.utcnow(),
        )

    async def get_benchmark_trends(
        self,
        prompt_id: uuid.UUID,
        days: int = 30,
    ) -> BenchmarkTrends:
        """Analyze benchmark trends for a prompt over time."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        query = (
            select(BenchmarkResult)
            .where(BenchmarkResult.prompt_id == prompt_id)
            .where(BenchmarkResult.executed_at >= cutoff)
            .order_by(BenchmarkResult.executed_at.asc())
        )
        result = await self.db.execute(query)
        benchmarks = list(result.scalars().all())

        if not benchmarks:
            return BenchmarkTrends(
                prompt_id=prompt_id,
                trend_data=[],
                rolling_avg_7d=None,
                rolling_avg_30d=None,
                score_delta_7d=None,
                score_delta_30d=None,
                is_regressing=False,
                regression_alert=None,
            )

        # Build trend data
        trend_data = [
            TrendPoint(
                timestamp=b.executed_at,
                score=b.overall_score,
                version=b.prompt_version,
                model_id=b.model_id,
            )
            for b in benchmarks
        ]

        # Calculate rolling averages
        now = datetime.utcnow()
        
        scores_7d = [
            b.overall_score 
            for b in benchmarks 
            if b.executed_at >= now - timedelta(days=7)
        ]
        scores_30d = [b.overall_score for b in benchmarks]

        rolling_avg_7d = sum(scores_7d) / len(scores_7d) if scores_7d else None
        rolling_avg_30d = sum(scores_30d) / len(scores_30d) if scores_30d else None

        # Calculate deltas
        first_7d = [
            b.overall_score 
            for b in benchmarks 
            if b.executed_at < now - timedelta(days=7)
        ]
        first_30d = [
            b.overall_score 
            for b in benchmarks 
            if b.executed_at < now - timedelta(days=30)
        ]

        score_delta_7d = None
        if first_7d and scores_7d:
            old_avg = sum(first_7d[-min(5, len(first_7d)):]) / min(5, len(first_7d))
            score_delta_7d = rolling_avg_7d - old_avg

        score_delta_30d = None
        if first_30d and rolling_avg_30d:
            old_avg = sum(first_30d[-min(10, len(first_30d)):]) / min(10, len(first_30d))
            score_delta_30d = rolling_avg_30d - old_avg

        # Detect regression
        is_regressing = False
        regression_alert = None
        
        if len(scores_7d) >= 3:
            recent_avg = sum(scores_7d[-3:]) / 3
            if rolling_avg_7d and recent_avg < rolling_avg_7d - 5:
                is_regressing = True
                regression_alert = f"Score dropped {rolling_avg_7d - recent_avg:.1f} points in last 7 days"

        return BenchmarkTrends(
            prompt_id=prompt_id,
            trend_data=trend_data,
            rolling_avg_7d=rolling_avg_7d,
            rolling_avg_30d=rolling_avg_30d,
            score_delta_7d=score_delta_7d,
            score_delta_30d=score_delta_30d,
            is_regressing=is_regressing,
            regression_alert=regression_alert,
        )

    async def check_regression_alerts(self) -> List[Dict[str, Any]]:
        """Check all active prompts for benchmark regressions."""
        # Get prompts with recent benchmarks
        cutoff = datetime.utcnow() - timedelta(days=7)
        
        query = (
            select(Prompt.id)
            .where(Prompt.last_benchmark_at >= cutoff)
            .where(Prompt.status == "active")
        )
        result = await self.db.execute(query)
        prompt_ids = [row[0] for row in result.fetchall()]

        alerts = []
        for prompt_id in prompt_ids:
            trends = await self.get_benchmark_trends(prompt_id)
            if trends.is_regressing and trends.regression_alert:
                alerts.append({
                    "prompt_id": str(prompt_id),
                    "alert": trends.regression_alert,
                    "rolling_avg_7d": trends.rolling_avg_7d,
                    "score_delta_7d": trends.score_delta_7d,
                })

        return alerts


# Suite management
class BenchmarkSuiteService:
    """Service for managing benchmark suites."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_suite(
        self,
        slug: str,
        name: str,
        owner_id: uuid.UUID,
        description: Optional[str] = None,
        test_cases: Optional[List[Dict]] = None,
        dimensions: Optional[List[str]] = None,
        weights: Optional[Dict[str, float]] = None,
        threshold: float = 80.0,
    ) -> BenchmarkSuite:
        """Create a new benchmark suite."""
        suite = BenchmarkSuite(
            slug=slug,
            name=name,
            description=description,
            test_cases=test_cases or [],
            dimensions=dimensions or ["quality", "safety", "performance", "clarity"],
            weights=weights or {"quality": 0.4, "safety": 0.3, "performance": 0.15, "clarity": 0.15},
            threshold=threshold,
            owner_id=owner_id,
        )
        self.db.add(suite)
        await self.db.flush()
        await self.db.refresh(suite)
        return suite

    async def get_suite(self, suite_id: uuid.UUID) -> Optional[BenchmarkSuite]:
        """Get suite by ID."""
        query = select(BenchmarkSuite).where(BenchmarkSuite.id == suite_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_suite_by_slug(self, slug: str) -> Optional[BenchmarkSuite]:
        """Get suite by slug."""
        query = select(BenchmarkSuite).where(BenchmarkSuite.slug == slug)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_suites(
        self,
        owner_id: Optional[uuid.UUID] = None,
        include_inactive: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[BenchmarkSuite], int]:
        """List benchmark suites with pagination."""
        query = select(BenchmarkSuite)
        
        if not include_inactive:
            query = query.where(BenchmarkSuite.is_active == True)
        if owner_id:
            query = query.where(BenchmarkSuite.owner_id == owner_id)
        
        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0
        
        # Apply pagination
        query = query.order_by(BenchmarkSuite.created_at.desc())
        query = query.limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        suites = list(result.scalars().all())
        
        return suites, total

    async def update_suite(
        self,
        suite_id: uuid.UUID,
        **kwargs,
    ) -> Optional[BenchmarkSuite]:
        """Update a benchmark suite."""
        suite = await self.get_suite(suite_id)
        if not suite:
            return None
        
        for key, value in kwargs.items():
            if hasattr(suite, key) and value is not None:
                setattr(suite, key, value)
        
        await self.db.flush()
        await self.db.refresh(suite)
        return suite

    async def add_test_case(
        self,
        suite_id: uuid.UUID,
        name: str,
        input_text: str,
        expected_output: Optional[str] = None,
        expected_patterns: Optional[List[str]] = None,
        weight: float = 1.0,
        category: Optional[str] = None,
    ) -> BenchmarkTestCase:
        """Add a test case to a suite."""
        test_case = BenchmarkTestCase(
            suite_id=suite_id,
            name=name,
            input_text=input_text,
            expected_output=expected_output,
            expected_patterns=expected_patterns or [],
            weight=weight,
            category=category,
        )
        self.db.add(test_case)
        await self.db.flush()
        await self.db.refresh(test_case)
        return test_case

    async def get_test_cases(self, suite_id: uuid.UUID) -> List[BenchmarkTestCase]:
        """Get all test cases for a suite."""
        query = (
            select(BenchmarkTestCase)
            .where(BenchmarkTestCase.suite_id == suite_id)
            .where(BenchmarkTestCase.is_active == True)
            .order_by(BenchmarkTestCase.created_at.asc())
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_default_suite(self) -> Optional[BenchmarkSuite]:
        """Get the default benchmark suite."""
        query = (
            select(BenchmarkSuite)
            .where(BenchmarkSuite.is_default == True)
            .where(BenchmarkSuite.is_active == True)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
