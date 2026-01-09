"""
ATE Integration

Integration with ARIA Testing & Evolution benchmark service.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import httpx

from hermes.config import get_settings

settings = get_settings()


@dataclass
class BenchmarkConfig:
    """Configuration for a benchmark run."""
    
    suite_id: str
    model_id: str
    model_version: Optional[str] = None
    dimensions: Optional[list[str]] = None
    timeout_seconds: int = 300


@dataclass
class BenchmarkScore:
    """Individual dimension score."""
    
    dimension: str
    score: float
    confidence: float
    details: Optional[dict] = None


@dataclass
class BenchmarkResult:
    """Result from an ATE benchmark run."""
    
    id: uuid.UUID
    prompt_id: uuid.UUID
    prompt_version: str
    suite_id: str
    overall_score: float
    dimension_scores: list[BenchmarkScore]
    model_id: str
    model_version: Optional[str]
    execution_time_ms: int
    token_usage: dict
    gate_passed: bool
    executed_at: datetime
    raw_results: Optional[dict] = None


class ATEClient:
    """Client for ATE benchmark service."""

    def __init__(self):
        self.grpc_url = settings.ate_grpc_url
        self.enabled = settings.ate_enabled
        self._client = httpx.AsyncClient(timeout=60.0)

    async def run_benchmark(
        self,
        prompt_content: str,
        prompt_id: uuid.UUID,
        prompt_version: str,
        config: BenchmarkConfig,
    ) -> BenchmarkResult:
        """Run a benchmark on a prompt using ATE."""
        if not self.enabled:
            # Return mock result when ATE is disabled
            return self._mock_result(prompt_id, prompt_version, config)

        # TODO: Implement actual gRPC call to ATE
        # For now, return mock result
        return self._mock_result(prompt_id, prompt_version, config)

    def _mock_result(
        self,
        prompt_id: uuid.UUID,
        prompt_version: str,
        config: BenchmarkConfig,
    ) -> BenchmarkResult:
        """Generate mock benchmark result for testing."""
        import random

        dimensions = config.dimensions or ["quality", "safety", "performance", "clarity"]
        dimension_scores = [
            BenchmarkScore(
                dimension=dim,
                score=random.uniform(0.7, 0.95),
                confidence=random.uniform(0.85, 0.99),
            )
            for dim in dimensions
        ]

        overall = sum(s.score for s in dimension_scores) / len(dimension_scores)

        return BenchmarkResult(
            id=uuid.uuid4(),
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            suite_id=config.suite_id,
            overall_score=overall * 100,
            dimension_scores=dimension_scores,
            model_id=config.model_id,
            model_version=config.model_version,
            execution_time_ms=random.randint(100, 500),
            token_usage={
                "input": random.randint(100, 500),
                "output": random.randint(200, 1000),
            },
            gate_passed=overall >= 0.8,
            executed_at=datetime.utcnow(),
        )

    async def get_suites(self) -> list[dict]:
        """Get available benchmark suites."""
        return [
            {
                "id": "default",
                "name": "Default Suite",
                "description": "Standard benchmark suite",
                "dimensions": ["quality", "safety", "performance", "clarity"],
            },
            {
                "id": "safety",
                "name": "Safety Suite",
                "description": "Safety-focused benchmarks",
                "dimensions": ["safety", "harmlessness", "refusal"],
            },
            {
                "id": "performance",
                "name": "Performance Suite",
                "description": "Performance benchmarks",
                "dimensions": ["latency", "token_efficiency", "accuracy"],
            },
        ]

    async def close(self):
        """Close HTTP client."""
        await self._client.aclose()
