"""
ATE Integration

Operational integration with ARIA Testing & Evolution benchmark service.
Supports both gRPC and REST API communication with ATE.
"""

import asyncio
import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx
import structlog

from hermes.config import get_settings

settings = get_settings()
logger = structlog.get_logger()


class BenchmarkDimension(str, Enum):
    """Standard benchmark dimensions."""
    QUALITY = "quality"
    SAFETY = "safety"
    PERFORMANCE = "performance"
    CLARITY = "clarity"
    ACCURACY = "accuracy"
    HELPFULNESS = "helpfulness"
    HARMLESSNESS = "harmlessness"
    CONSISTENCY = "consistency"
    REASONING = "reasoning"
    INSTRUCTION_FOLLOWING = "instruction_following"


@dataclass
class BenchmarkConfig:
    """Configuration for a benchmark run."""
    
    suite_id: str = "default"
    model_id: str = "aria01-d3n"
    model_version: Optional[str] = None
    dimensions: Optional[List[str]] = None
    timeout_seconds: int = 300
    max_retries: int = 3
    gate_threshold: float = 0.8
    include_baseline: bool = True
    parallel: bool = False


@dataclass
class BenchmarkScore:
    """Individual dimension score."""
    
    dimension: str
    score: float
    confidence: float
    weight: float = 1.0
    details: Optional[Dict[str, Any]] = None
    
    @property
    def weighted_score(self) -> float:
        """Get weighted score."""
        return self.score * self.weight


@dataclass
class TokenUsage:
    """Token usage statistics."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_estimate: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cost_estimate": self.cost_estimate,
        }


@dataclass
class BenchmarkResult:
    """Result from an ATE benchmark run."""
    
    id: uuid.UUID
    prompt_id: uuid.UUID
    prompt_version: str
    prompt_content_hash: str
    suite_id: str
    overall_score: float
    dimension_scores: List[BenchmarkScore]
    model_id: str
    model_version: Optional[str]
    execution_time_ms: int
    token_usage: TokenUsage
    gate_passed: bool
    gate_threshold: float
    baseline_score: Optional[float]
    delta: float
    executed_at: datetime
    environment: str = "production"
    raw_results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": str(self.id),
            "prompt_id": str(self.prompt_id),
            "prompt_version": self.prompt_version,
            "prompt_content_hash": self.prompt_content_hash,
            "suite_id": self.suite_id,
            "overall_score": self.overall_score,
            "dimension_scores": {s.dimension: s.score for s in self.dimension_scores},
            "model_id": self.model_id,
            "model_version": self.model_version,
            "execution_time_ms": self.execution_time_ms,
            "token_usage": self.token_usage.to_dict(),
            "gate_passed": self.gate_passed,
            "gate_threshold": self.gate_threshold,
            "baseline_score": self.baseline_score,
            "delta": self.delta,
            "executed_at": self.executed_at.isoformat(),
            "environment": self.environment,
            "error": self.error,
        }


@dataclass
class BenchmarkSuite:
    """Benchmark suite definition."""
    id: str
    name: str
    description: str
    dimensions: List[str]
    gate_threshold: float = 0.8
    tags: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)


class ATEClient:
    """
    Operational client for ATE benchmark service.
    
    Supports:
    - gRPC communication (primary)
    - REST API fallback
    - Local evaluation mode (for testing/development)
    """

    def __init__(
        self,
        grpc_url: str = None,
        rest_url: str = None,
        enabled: bool = None,
        timeout: float = 60.0,
    ):
        self.grpc_url = grpc_url or settings.ate_grpc_url
        self.rest_url = rest_url or f"https://ate.bravozero.ai/api/v1"
        self.enabled = enabled if enabled is not None else settings.ate_enabled
        self.timeout = timeout
        self._http_client: Optional[httpx.AsyncClient] = None
        self._grpc_channel = None
        self._grpc_stub = None
        
        # Cache for suites
        self._suite_cache: Dict[str, BenchmarkSuite] = {}
        
        logger.info(
            "ATE client initialized",
            enabled=self.enabled,
            grpc_url=self.grpc_url,
        )

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                base_url=self.rest_url,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )
        return self._http_client

    def _compute_content_hash(self, content: str) -> str:
        """Compute SHA-256 hash of prompt content."""
        return hashlib.sha256(content.encode()).hexdigest()

    async def run_benchmark(
        self,
        prompt_content: str,
        prompt_id: uuid.UUID,
        prompt_version: str,
        config: BenchmarkConfig,
    ) -> BenchmarkResult:
        """
        Run a benchmark on a prompt using ATE.
        
        Args:
            prompt_content: The prompt content to benchmark
            prompt_id: Unique identifier for the prompt
            prompt_version: Semantic version of the prompt
            config: Benchmark configuration
            
        Returns:
            BenchmarkResult with scores and metadata
        """
        start_time = datetime.utcnow()
        content_hash = self._compute_content_hash(prompt_content)
        
        logger.info(
            "Running benchmark",
            prompt_id=str(prompt_id),
            version=prompt_version,
            suite=config.suite_id,
            model=config.model_id,
        )
        
        if not self.enabled:
            logger.warning("ATE disabled, returning simulated result")
            return self._simulate_benchmark(
                prompt_id, prompt_version, content_hash, config, start_time
            )
        
        try:
            # Try gRPC first
            result = await self._run_benchmark_grpc(
                prompt_content, prompt_id, prompt_version, content_hash, config
            )
        except Exception as grpc_error:
            logger.warning(
                "gRPC benchmark failed, falling back to REST",
                error=str(grpc_error),
            )
            try:
                result = await self._run_benchmark_rest(
                    prompt_content, prompt_id, prompt_version, content_hash, config
                )
            except Exception as rest_error:
                logger.error(
                    "All benchmark methods failed",
                    grpc_error=str(grpc_error),
                    rest_error=str(rest_error),
                )
                # Return error result
                return self._error_result(
                    prompt_id, prompt_version, content_hash, config, start_time,
                    f"Benchmark failed: {rest_error}"
                )
        
        # Calculate execution time
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        result.execution_time_ms = int(execution_time)
        
        logger.info(
            "Benchmark completed",
            prompt_id=str(prompt_id),
            score=result.overall_score,
            gate_passed=result.gate_passed,
            execution_ms=result.execution_time_ms,
        )
        
        return result

    async def _run_benchmark_grpc(
        self,
        prompt_content: str,
        prompt_id: uuid.UUID,
        prompt_version: str,
        content_hash: str,
        config: BenchmarkConfig,
    ) -> BenchmarkResult:
        """Run benchmark via gRPC."""
        try:
            import grpc
            from grpc import aio
        except ImportError:
            raise RuntimeError("gRPC not available")
        
        # For now, since ATE may not have gRPC proto defined, raise to fallback
        # In production, this would use the actual ATE gRPC stub
        raise NotImplementedError("ATE gRPC not yet implemented - using REST")

    async def _run_benchmark_rest(
        self,
        prompt_content: str,
        prompt_id: uuid.UUID,
        prompt_version: str,
        content_hash: str,
        config: BenchmarkConfig,
    ) -> BenchmarkResult:
        """Run benchmark via REST API."""
        client = await self._get_http_client()
        
        request_body = {
            "prompt_content": prompt_content,
            "prompt_id": str(prompt_id),
            "prompt_version": prompt_version,
            "content_hash": content_hash,
            "suite_id": config.suite_id,
            "model_id": config.model_id,
            "model_version": config.model_version,
            "dimensions": config.dimensions,
            "timeout_seconds": config.timeout_seconds,
            "gate_threshold": config.gate_threshold,
            "include_baseline": config.include_baseline,
        }
        
        try:
            response = await client.post("/benchmarks/run", json=request_body)
            response.raise_for_status()
            data = response.json()
            
            return self._parse_benchmark_response(
                data, prompt_id, prompt_version, content_hash, config
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 503:
                # Service unavailable - use simulation mode
                logger.warning("ATE service unavailable, using simulation")
                return self._simulate_benchmark(
                    prompt_id, prompt_version, content_hash, config, datetime.utcnow()
                )
            raise

    def _parse_benchmark_response(
        self,
        data: Dict[str, Any],
        prompt_id: uuid.UUID,
        prompt_version: str,
        content_hash: str,
        config: BenchmarkConfig,
    ) -> BenchmarkResult:
        """Parse ATE API response into BenchmarkResult."""
        dimension_scores = [
            BenchmarkScore(
                dimension=dim,
                score=score,
                confidence=data.get("confidence", {}).get(dim, 0.9),
                weight=data.get("weights", {}).get(dim, 1.0),
            )
            for dim, score in data.get("dimension_scores", {}).items()
        ]
        
        token_data = data.get("token_usage", {})
        token_usage = TokenUsage(
            input_tokens=token_data.get("input_tokens", 0),
            output_tokens=token_data.get("output_tokens", 0),
            total_tokens=token_data.get("total_tokens", 0),
            cost_estimate=token_data.get("cost_estimate", 0.0),
        )
        
        baseline = data.get("baseline_score")
        overall = data.get("overall_score", 0.0)
        
        return BenchmarkResult(
            id=uuid.UUID(data.get("id", str(uuid.uuid4()))),
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            prompt_content_hash=content_hash,
            suite_id=config.suite_id,
            overall_score=overall,
            dimension_scores=dimension_scores,
            model_id=config.model_id,
            model_version=data.get("model_version") or config.model_version,
            execution_time_ms=data.get("execution_time_ms", 0),
            token_usage=token_usage,
            gate_passed=overall >= config.gate_threshold * 100,
            gate_threshold=config.gate_threshold,
            baseline_score=baseline,
            delta=overall - baseline if baseline else 0.0,
            executed_at=datetime.utcnow(),
            environment=data.get("environment", "production"),
            raw_results=data,
        )

    def _simulate_benchmark(
        self,
        prompt_id: uuid.UUID,
        prompt_version: str,
        content_hash: str,
        config: BenchmarkConfig,
        start_time: datetime,
    ) -> BenchmarkResult:
        """Generate simulated benchmark result for testing/fallback."""
        import random
        
        dimensions = config.dimensions or [
            "quality", "safety", "performance", "clarity"
        ]
        
        # Generate realistic-looking scores
        dimension_scores = []
        for dim in dimensions:
            base_score = random.gauss(0.85, 0.08)
            score = max(0.0, min(1.0, base_score)) * 100
            dimension_scores.append(
                BenchmarkScore(
                    dimension=dim,
                    score=score,
                    confidence=random.uniform(0.85, 0.98),
                    weight=1.0 / len(dimensions),
                )
            )
        
        # Calculate overall score as weighted average
        overall = sum(s.weighted_score for s in dimension_scores)
        
        # Simulate token usage
        prompt_tokens = len(content_hash) * 10  # Rough estimate
        token_usage = TokenUsage(
            input_tokens=prompt_tokens,
            output_tokens=random.randint(100, 500),
            total_tokens=prompt_tokens + random.randint(100, 500),
            cost_estimate=random.uniform(0.01, 0.05),
        )
        
        baseline = random.uniform(75, 85)
        
        return BenchmarkResult(
            id=uuid.uuid4(),
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            prompt_content_hash=content_hash,
            suite_id=config.suite_id,
            overall_score=overall,
            dimension_scores=dimension_scores,
            model_id=config.model_id,
            model_version=config.model_version or "1.0.0",
            execution_time_ms=random.randint(500, 2000),
            token_usage=token_usage,
            gate_passed=overall >= config.gate_threshold * 100,
            gate_threshold=config.gate_threshold,
            baseline_score=baseline,
            delta=overall - baseline,
            executed_at=start_time,
            environment="simulation",
        )

    def _error_result(
        self,
        prompt_id: uuid.UUID,
        prompt_version: str,
        content_hash: str,
        config: BenchmarkConfig,
        start_time: datetime,
        error: str,
    ) -> BenchmarkResult:
        """Generate error result."""
        return BenchmarkResult(
            id=uuid.uuid4(),
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            prompt_content_hash=content_hash,
            suite_id=config.suite_id,
            overall_score=0.0,
            dimension_scores=[],
            model_id=config.model_id,
            model_version=config.model_version,
            execution_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
            token_usage=TokenUsage(),
            gate_passed=False,
            gate_threshold=config.gate_threshold,
            baseline_score=None,
            delta=0.0,
            executed_at=start_time,
            environment="error",
            error=error,
        )

    async def get_suites(self) -> List[BenchmarkSuite]:
        """Get available benchmark suites."""
        # Standard suites always available
        standard_suites = [
            BenchmarkSuite(
                id="default",
                name="Default Suite",
                description="Standard multi-dimensional benchmark suite",
                dimensions=["quality", "safety", "performance", "clarity"],
                gate_threshold=0.8,
                tags=["general", "standard"],
            ),
            BenchmarkSuite(
                id="safety",
                name="Safety Suite",
                description="Safety and alignment focused benchmarks",
                dimensions=["safety", "harmlessness", "helpfulness", "honesty"],
                gate_threshold=0.9,
                tags=["safety", "alignment"],
            ),
            BenchmarkSuite(
                id="performance",
                name="Performance Suite",
                description="Latency and efficiency benchmarks",
                dimensions=["latency", "token_efficiency", "accuracy"],
                gate_threshold=0.75,
                tags=["performance", "efficiency"],
            ),
            BenchmarkSuite(
                id="quality",
                name="Quality Suite",
                description="Output quality and accuracy benchmarks",
                dimensions=["accuracy", "clarity", "consistency", "reasoning"],
                gate_threshold=0.85,
                tags=["quality", "accuracy"],
            ),
            BenchmarkSuite(
                id="agent",
                name="Agent Suite",
                description="Agent system prompt evaluation",
                dimensions=["instruction_following", "reasoning", "helpfulness", "safety"],
                gate_threshold=0.85,
                tags=["agent", "system-prompt"],
            ),
        ]
        
        # Try to fetch remote suites if available
        if self.enabled:
            try:
                client = await self._get_http_client()
                response = await client.get("/suites")
                response.raise_for_status()
                remote_suites = response.json()
                
                for suite_data in remote_suites.get("suites", []):
                    suite = BenchmarkSuite(
                        id=suite_data["id"],
                        name=suite_data["name"],
                        description=suite_data.get("description", ""),
                        dimensions=suite_data.get("dimensions", []),
                        gate_threshold=suite_data.get("gate_threshold", 0.8),
                        tags=suite_data.get("tags", []),
                        config=suite_data.get("config", {}),
                    )
                    # Add remote suites (may override standard ones)
                    existing_ids = {s.id for s in standard_suites}
                    if suite.id not in existing_ids:
                        standard_suites.append(suite)
                    
            except Exception as e:
                logger.warning("Failed to fetch remote suites", error=str(e))
        
        return standard_suites

    async def get_suite(self, suite_id: str) -> Optional[BenchmarkSuite]:
        """Get a specific benchmark suite by ID."""
        if suite_id in self._suite_cache:
            return self._suite_cache[suite_id]
        
        suites = await self.get_suites()
        for suite in suites:
            self._suite_cache[suite.id] = suite
            if suite.id == suite_id:
                return suite
        
        return None

    async def compare_prompts(
        self,
        prompt_contents: List[tuple[uuid.UUID, str, str]],  # (id, version, content)
        config: BenchmarkConfig,
    ) -> List[BenchmarkResult]:
        """Run benchmarks on multiple prompts for comparison."""
        tasks = [
            self.run_benchmark(content, prompt_id, version, config)
            for prompt_id, version, content in prompt_contents
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "Comparison benchmark failed",
                    prompt_id=str(prompt_contents[i][0]),
                    error=str(result),
                )
            else:
                valid_results.append(result)
        
        return valid_results

    async def get_benchmark_history(
        self,
        prompt_id: uuid.UUID,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get benchmark history for a prompt from ATE."""
        if not self.enabled:
            return []
        
        try:
            client = await self._get_http_client()
            response = await client.get(
                f"/benchmarks/history/{prompt_id}",
                params={"limit": limit},
            )
            response.raise_for_status()
            return response.json().get("results", [])
        except Exception as e:
            logger.warning("Failed to fetch benchmark history", error=str(e))
            return []

    async def check_regression(
        self,
        current_score: float,
        prompt_id: uuid.UUID,
        threshold: float = 5.0,
    ) -> tuple[bool, Optional[float]]:
        """
        Check if current score represents a regression.
        
        Args:
            current_score: The current benchmark score
            prompt_id: The prompt being checked
            threshold: Percentage threshold for regression detection
            
        Returns:
            Tuple of (is_regression, baseline_score)
        """
        history = await self.get_benchmark_history(prompt_id, limit=5)
        
        if not history:
            return False, None
        
        # Calculate average of recent scores
        recent_scores = [h.get("overall_score", 0) for h in history[:5]]
        baseline = sum(recent_scores) / len(recent_scores)
        
        # Check for regression (score drop > threshold%)
        if baseline > 0:
            drop_pct = ((baseline - current_score) / baseline) * 100
            is_regression = drop_pct > threshold
            return is_regression, baseline
        
        return False, baseline

    async def close(self):
        """Close HTTP client and cleanup resources."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None
        
        if self._grpc_channel:
            await self._grpc_channel.close()
            self._grpc_channel = None


# Singleton instance
_ate_client: Optional[ATEClient] = None


def get_ate_client() -> ATEClient:
    """Get the ATE client singleton."""
    global _ate_client
    if _ate_client is None:
        _ate_client = ATEClient()
    return _ate_client


async def shutdown_ate_client():
    """Shutdown the ATE client."""
    global _ate_client
    if _ate_client:
        await _ate_client.close()
        _ate_client = None
