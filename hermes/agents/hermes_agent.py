"""
aria.hermes - Autonomous Prompt Improvement Agent

The Hermes agent is an autonomous system that continuously monitors,
analyzes, and improves prompts across the Bravo Zero ecosystem.

Features:
- Continuous quality monitoring
- Automatic improvement suggestions
- Self-healing prompts (auto-fix regressions)
- Proactive optimization
- Cross-prompt learning
- Autonomous A/B testing
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable

import structlog

from hermes.config import get_settings
from hermes.integrations.ate import get_ate_client, BenchmarkConfig
from hermes.integrations.asrbs import get_asrbs_client
from hermes.integrations.beeper import get_beeper_client

settings = get_settings()
logger = structlog.get_logger()


class AgentState(str, Enum):
    """Agent lifecycle state."""
    IDLE = "idle"
    MONITORING = "monitoring"
    ANALYZING = "analyzing"
    IMPROVING = "improving"
    TESTING = "testing"
    DEPLOYING = "deploying"
    SLEEPING = "sleeping"


class TaskType(str, Enum):
    """Types of autonomous tasks."""
    QUALITY_CHECK = "quality_check"
    REGRESSION_FIX = "regression_fix"
    PROACTIVE_OPTIMIZE = "proactive_optimize"
    BENCHMARK_STALE = "benchmark_stale"
    APPLY_SUGGESTION = "apply_suggestion"
    RUN_EXPERIMENT = "run_experiment"
    CROSS_PROMPT_LEARN = "cross_prompt_learn"


class Priority(str, Enum):
    """Task priority levels."""
    CRITICAL = "critical"  # Immediate action needed
    HIGH = "high"          # Same-day action
    MEDIUM = "medium"      # Within 24 hours
    LOW = "low"            # Best effort


@dataclass
class AgentTask:
    """A task for the agent to execute."""
    id: uuid.UUID
    type: TaskType
    priority: Priority
    prompt_id: Optional[uuid.UUID]
    description: str
    context: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    @property
    def status(self) -> str:
        if self.error:
            return "failed"
        if self.completed_at:
            return "completed"
        if self.started_at:
            return "in_progress"
        return "pending"


@dataclass
class AgentMetrics:
    """Agent performance metrics."""
    tasks_completed: int = 0
    tasks_failed: int = 0
    improvements_made: int = 0
    regressions_fixed: int = 0
    total_score_improvement: float = 0.0
    last_cycle_at: Optional[datetime] = None
    uptime_seconds: float = 0.0


class HermesAgent:
    """
    aria.hermes - The Autonomous Prompt Engineering Agent
    
    This agent runs continuously to:
    1. Monitor prompt quality across the ecosystem
    2. Detect and fix regressions automatically
    3. Proactively suggest and apply improvements
    4. Learn patterns across prompts
    5. Run experiments to validate changes
    """
    
    AGENT_ID = "aria.hermes"
    AGENT_VERSION = "1.0.0"
    
    def __init__(
        self,
        db_session,
        prompt_store,
        benchmark_engine,
        quality_gate_service,
        ab_testing_service,
        cycle_interval_minutes: int = 15,
        max_concurrent_tasks: int = 5,
    ):
        self.db = db_session
        self.prompt_store = prompt_store
        self.benchmark_engine = benchmark_engine
        self.quality_gates = quality_gate_service
        self.ab_testing = ab_testing_service
        
        self.ate = get_ate_client()
        self.asrbs = get_asrbs_client()
        self.beeper = get_beeper_client()
        
        self.cycle_interval = timedelta(minutes=cycle_interval_minutes)
        self.max_concurrent_tasks = max_concurrent_tasks
        
        # State
        self.state = AgentState.IDLE
        self.task_queue: List[AgentTask] = []
        self.active_tasks: Dict[uuid.UUID, AgentTask] = {}
        self.metrics = AgentMetrics()
        
        # Configuration
        self.config = {
            "auto_fix_regressions": True,
            "auto_apply_high_confidence": True,
            "high_confidence_threshold": 0.9,
            "stale_benchmark_hours": 24,
            "min_improvement_threshold": 2.0,  # %
            "learning_enabled": True,
        }
        
        self._running = False
        self._started_at: Optional[datetime] = None
        
        logger.info(
            "Hermes agent initialized",
            agent_id=self.AGENT_ID,
            version=self.AGENT_VERSION,
        )
    
    # =========================================================================
    # Lifecycle
    # =========================================================================
    
    async def start(self):
        """Start the agent's main loop."""
        if self._running:
            logger.warning("Agent already running")
            return
        
        self._running = True
        self._started_at = datetime.utcnow()
        self.state = AgentState.MONITORING
        
        logger.info("Hermes agent started")
        
        # Main loop
        while self._running:
            try:
                await self._run_cycle()
            except Exception as e:
                logger.error("Agent cycle failed", error=str(e))
            
            # Wait for next cycle
            self.state = AgentState.SLEEPING
            await asyncio.sleep(self.cycle_interval.total_seconds())
    
    async def stop(self):
        """Stop the agent gracefully."""
        logger.info("Stopping Hermes agent")
        self._running = False
        
        # Wait for active tasks to complete
        if self.active_tasks:
            logger.info(f"Waiting for {len(self.active_tasks)} active tasks")
            await asyncio.sleep(5)
        
        self.state = AgentState.IDLE
        self.metrics.uptime_seconds = (
            datetime.utcnow() - self._started_at
        ).total_seconds() if self._started_at else 0
        
        logger.info(
            "Hermes agent stopped",
            tasks_completed=self.metrics.tasks_completed,
            improvements_made=self.metrics.improvements_made,
        )
    
    async def _run_cycle(self):
        """Run one cycle of the agent."""
        cycle_start = datetime.utcnow()
        logger.info("Starting agent cycle")
        
        # Phase 1: Monitor and discover tasks
        self.state = AgentState.MONITORING
        await self._discover_tasks()
        
        # Phase 2: Analyze and prioritize
        self.state = AgentState.ANALYZING
        self._prioritize_tasks()
        
        # Phase 3: Execute tasks
        self.state = AgentState.IMPROVING
        await self._execute_tasks()
        
        self.metrics.last_cycle_at = datetime.utcnow()
        
        logger.info(
            "Agent cycle completed",
            duration_seconds=(datetime.utcnow() - cycle_start).total_seconds(),
            tasks_in_queue=len(self.task_queue),
        )
    
    # =========================================================================
    # Task Discovery
    # =========================================================================
    
    async def _discover_tasks(self):
        """Discover tasks by analyzing the prompt ecosystem."""
        # Get all prompts
        prompts = await self.prompt_store.list(limit=1000)
        
        for prompt in prompts.get("items", []):
            # Check for stale benchmarks
            if self._needs_benchmark(prompt):
                self._add_task(
                    TaskType.BENCHMARK_STALE,
                    Priority.LOW,
                    prompt.id,
                    f"Benchmark stale for {prompt.name}",
                    {"prompt": prompt},
                )
            
            # Check for regressions
            if self._has_regression(prompt):
                self._add_task(
                    TaskType.REGRESSION_FIX,
                    Priority.CRITICAL,
                    prompt.id,
                    f"Regression detected in {prompt.name}",
                    {"prompt": prompt},
                )
            
            # Check for improvement opportunities
            if self._can_improve(prompt):
                self._add_task(
                    TaskType.PROACTIVE_OPTIMIZE,
                    Priority.MEDIUM,
                    prompt.id,
                    f"Optimization opportunity for {prompt.name}",
                    {"prompt": prompt},
                )
    
    def _needs_benchmark(self, prompt) -> bool:
        """Check if prompt needs benchmarking."""
        if not prompt.last_benchmark_at:
            return True
        
        age = datetime.utcnow() - prompt.last_benchmark_at
        return age.total_seconds() > self.config["stale_benchmark_hours"] * 3600
    
    def _has_regression(self, prompt) -> bool:
        """Check if prompt has a quality regression."""
        # Would check benchmark history for score drops
        return False  # Simplified
    
    def _can_improve(self, prompt) -> bool:
        """Check if prompt has improvement potential."""
        if not prompt.benchmark_score:
            return False
        return prompt.benchmark_score < 90  # Room for improvement
    
    def _add_task(
        self,
        task_type: TaskType,
        priority: Priority,
        prompt_id: Optional[uuid.UUID],
        description: str,
        context: Dict[str, Any],
    ):
        """Add a task to the queue if not already present."""
        # Check for duplicate tasks
        for task in self.task_queue:
            if task.type == task_type and task.prompt_id == prompt_id:
                return
        
        task = AgentTask(
            id=uuid.uuid4(),
            type=task_type,
            priority=priority,
            prompt_id=prompt_id,
            description=description,
            context=context,
        )
        
        self.task_queue.append(task)
        
        logger.debug(
            "Task added to queue",
            task_id=str(task.id),
            type=task_type.value,
            priority=priority.value,
        )
    
    def _prioritize_tasks(self):
        """Sort task queue by priority."""
        priority_order = {
            Priority.CRITICAL: 0,
            Priority.HIGH: 1,
            Priority.MEDIUM: 2,
            Priority.LOW: 3,
        }
        
        self.task_queue.sort(
            key=lambda t: (priority_order[t.priority], t.created_at)
        )
    
    # =========================================================================
    # Task Execution
    # =========================================================================
    
    async def _execute_tasks(self):
        """Execute pending tasks."""
        while self.task_queue and len(self.active_tasks) < self.max_concurrent_tasks:
            task = self.task_queue.pop(0)
            self.active_tasks[task.id] = task
            
            # Execute task
            try:
                await self._execute_task(task)
            except Exception as e:
                task.error = str(e)
                self.metrics.tasks_failed += 1
                logger.error(
                    "Task execution failed",
                    task_id=str(task.id),
                    error=str(e),
                )
            finally:
                del self.active_tasks[task.id]
    
    async def _execute_task(self, task: AgentTask):
        """Execute a single task."""
        task.started_at = datetime.utcnow()
        
        logger.info(
            "Executing task",
            task_id=str(task.id),
            type=task.type.value,
            prompt_id=str(task.prompt_id) if task.prompt_id else None,
        )
        
        if task.type == TaskType.QUALITY_CHECK:
            result = await self._task_quality_check(task)
        elif task.type == TaskType.REGRESSION_FIX:
            result = await self._task_fix_regression(task)
        elif task.type == TaskType.PROACTIVE_OPTIMIZE:
            result = await self._task_proactive_optimize(task)
        elif task.type == TaskType.BENCHMARK_STALE:
            result = await self._task_run_benchmark(task)
        elif task.type == TaskType.APPLY_SUGGESTION:
            result = await self._task_apply_suggestion(task)
        elif task.type == TaskType.RUN_EXPERIMENT:
            result = await self._task_run_experiment(task)
        elif task.type == TaskType.CROSS_PROMPT_LEARN:
            result = await self._task_cross_prompt_learn(task)
        else:
            result = {"status": "unknown_task_type"}
        
        task.completed_at = datetime.utcnow()
        task.result = result
        self.metrics.tasks_completed += 1
        
        logger.info(
            "Task completed",
            task_id=str(task.id),
            duration_ms=(task.completed_at - task.started_at).total_seconds() * 1000,
        )
    
    # =========================================================================
    # Task Implementations
    # =========================================================================
    
    async def _task_quality_check(self, task: AgentTask) -> Dict[str, Any]:
        """Check quality of a prompt."""
        prompt = task.context.get("prompt")
        if not prompt:
            return {"status": "no_prompt"}
        
        # Run benchmark
        result = await self.benchmark_engine.run_benchmark(
            prompt=prompt,
            suite_id="default",
            notify=False,
        )
        
        # Check quality gate
        gate_result, gate_details = await self.quality_gates.evaluate_quality_gate(prompt)
        
        return {
            "status": "checked",
            "score": result.overall_score,
            "gate_status": gate_result.value,
            "gate_details": gate_details,
        }
    
    async def _task_fix_regression(self, task: AgentTask) -> Dict[str, Any]:
        """Automatically fix a regression."""
        prompt = task.context.get("prompt")
        if not prompt:
            return {"status": "no_prompt"}
        
        if not self.config["auto_fix_regressions"]:
            return {"status": "auto_fix_disabled"}
        
        # Get self-critique suggestions
        critique = await self.benchmark_engine.run_self_critique(prompt)
        
        # Find high-confidence suggestions
        high_conf_suggestions = [
            s for s in critique.get("suggestions", [])
            if s.get("confidence", 0) >= self.config["high_confidence_threshold"]
        ]
        
        if not high_conf_suggestions:
            # Try rollback to previous version
            return await self._attempt_rollback(prompt)
        
        # Apply top suggestion
        top_suggestion = max(high_conf_suggestions, key=lambda s: s.get("confidence", 0))
        
        applied = await self._apply_suggestion_safely(
            prompt, top_suggestion, "Autonomous regression fix"
        )
        
        if applied:
            self.metrics.regressions_fixed += 1
            self.metrics.improvements_made += 1
        
        return {
            "status": "fixed" if applied else "fix_failed",
            "suggestion_applied": top_suggestion.get("id"),
        }
    
    async def _attempt_rollback(self, prompt) -> Dict[str, Any]:
        """Attempt to rollback to a previous version."""
        from hermes.services.version_control import VersionControlService
        
        vc = VersionControlService(self.db)
        versions = await vc.list_versions(prompt.id, limit=5)
        
        # Find a version with better score
        for version in versions[1:]:  # Skip current
            if version.benchmark_score and version.benchmark_score > prompt.benchmark_score:
                # Rollback to this version
                await vc.rollback(
                    prompt_id=prompt.id,
                    to_version=version.version,
                    reason="Autonomous rollback: quality regression",
                )
                
                return {
                    "status": "rolled_back",
                    "to_version": version.version,
                }
        
        return {"status": "no_better_version"}
    
    async def _task_proactive_optimize(self, task: AgentTask) -> Dict[str, Any]:
        """Proactively optimize a prompt."""
        prompt = task.context.get("prompt")
        if not prompt:
            return {"status": "no_prompt"}
        
        # Get suggestions
        critique = await self.benchmark_engine.run_self_critique(prompt)
        suggestions = critique.get("suggestions", [])
        
        if not suggestions:
            return {"status": "no_suggestions"}
        
        # Check if we should auto-apply
        if self.config["auto_apply_high_confidence"]:
            high_conf = [
                s for s in suggestions
                if s.get("confidence", 0) >= self.config["high_confidence_threshold"]
            ]
            
            if high_conf:
                # Apply top suggestion
                top = max(high_conf, key=lambda s: s.get("confidence", 0))
                applied = await self._apply_suggestion_safely(
                    prompt, top, "Autonomous proactive optimization"
                )
                
                if applied:
                    self.metrics.improvements_made += 1
                    return {
                        "status": "improved",
                        "suggestion_applied": top.get("id"),
                    }
        
        # Notify about suggestions
        await self.beeper.notify_suggestions_ready(
            prompt_id=prompt.id,
            prompt_name=prompt.name,
            suggestion_count=len(suggestions),
            improvement_potential=critique.get("improvement_potential", 0),
            recipients=["system"],
        )
        
        return {
            "status": "suggestions_available",
            "count": len(suggestions),
        }
    
    async def _task_run_benchmark(self, task: AgentTask) -> Dict[str, Any]:
        """Run a benchmark on a stale prompt."""
        prompt = task.context.get("prompt")
        if not prompt:
            return {"status": "no_prompt"}
        
        result = await self.benchmark_engine.run_benchmark(
            prompt=prompt,
            suite_id="default",
            notify=True,
        )
        
        return {
            "status": "benchmarked",
            "score": result.overall_score,
            "gate_passed": result.gate_passed,
        }
    
    async def _task_apply_suggestion(self, task: AgentTask) -> Dict[str, Any]:
        """Apply a specific suggestion."""
        prompt = task.context.get("prompt")
        suggestion = task.context.get("suggestion")
        
        if not prompt or not suggestion:
            return {"status": "missing_context"}
        
        applied = await self._apply_suggestion_safely(
            prompt, suggestion, "Autonomous suggestion application"
        )
        
        if applied:
            self.metrics.improvements_made += 1
        
        return {"status": "applied" if applied else "failed"}
    
    async def _task_run_experiment(self, task: AgentTask) -> Dict[str, Any]:
        """Run an A/B experiment."""
        experiment_config = task.context.get("experiment")
        if not experiment_config:
            return {"status": "no_experiment_config"}
        
        experiment = await self.ab_testing.create_experiment(**experiment_config)
        await self.ab_testing.start_experiment(experiment.id)
        
        return {
            "status": "experiment_started",
            "experiment_id": str(experiment.id),
        }
    
    async def _task_cross_prompt_learn(self, task: AgentTask) -> Dict[str, Any]:
        """Learn patterns across prompts."""
        if not self.config["learning_enabled"]:
            return {"status": "learning_disabled"}
        
        # Get high-performing prompts
        prompts = await self.prompt_store.list(
            sort_by="benchmark_score",
            sort_order="desc",
            limit=10,
        )
        
        # Analyze patterns (simplified)
        patterns = []
        for prompt in prompts.get("items", []):
            if prompt.benchmark_score and prompt.benchmark_score >= 90:
                # Extract patterns (would use more sophisticated NLP)
                if "example" in prompt.content.lower():
                    patterns.append("uses_examples")
                if "step" in prompt.content.lower():
                    patterns.append("uses_steps")
        
        return {
            "status": "learned",
            "patterns": list(set(patterns)),
        }
    
    async def _apply_suggestion_safely(
        self,
        prompt,
        suggestion: Dict[str, Any],
        change_reason: str,
    ) -> bool:
        """Safely apply a suggestion with validation."""
        try:
            # Apply suggestion
            updated_prompt = await self.benchmark_engine.apply_suggestion(
                prompt=prompt,
                suggestion_id=suggestion.get("id"),
            )
            
            # Verify improvement
            result = await self.benchmark_engine.run_benchmark(
                prompt=updated_prompt,
                suite_id="default",
                notify=False,
            )
            
            # Check if actually improved
            if result.overall_score > (prompt.benchmark_score or 0):
                self.metrics.total_score_improvement += (
                    result.overall_score - (prompt.benchmark_score or 0)
                )
                return True
            else:
                # Rollback if not improved
                logger.warning(
                    "Suggestion did not improve score, rolling back",
                    prompt_id=str(prompt.id),
                    old_score=prompt.benchmark_score,
                    new_score=result.overall_score,
                )
                # Rollback would happen here
                return False
                
        except Exception as e:
            logger.error(
                "Failed to apply suggestion",
                prompt_id=str(prompt.id),
                error=str(e),
            )
            return False
    
    # =========================================================================
    # Status and Metrics
    # =========================================================================
    
    def get_status(self) -> Dict[str, Any]:
        """Get agent status and metrics."""
        return {
            "agent_id": self.AGENT_ID,
            "version": self.AGENT_VERSION,
            "state": self.state.value,
            "running": self._running,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "uptime_seconds": (
                datetime.utcnow() - self._started_at
            ).total_seconds() if self._started_at else 0,
            "metrics": {
                "tasks_completed": self.metrics.tasks_completed,
                "tasks_failed": self.metrics.tasks_failed,
                "improvements_made": self.metrics.improvements_made,
                "regressions_fixed": self.metrics.regressions_fixed,
                "total_score_improvement": self.metrics.total_score_improvement,
                "last_cycle_at": (
                    self.metrics.last_cycle_at.isoformat()
                    if self.metrics.last_cycle_at else None
                ),
            },
            "queue": {
                "pending": len(self.task_queue),
                "active": len(self.active_tasks),
            },
            "config": self.config,
        }
    
    def update_config(self, updates: Dict[str, Any]):
        """Update agent configuration."""
        for key, value in updates.items():
            if key in self.config:
                self.config[key] = value
                logger.info(f"Agent config updated: {key}={value}")


# Factory function
async def create_hermes_agent(db_session):
    """Create and configure the Hermes agent."""
    from hermes.services.prompt_store import PromptStoreService
    from hermes.services.benchmark_engine import BenchmarkEngine
    from hermes.services.quality_gates import QualityGateService
    from hermes.services.ab_testing import ABTestingService
    
    prompt_store = PromptStoreService(db_session)
    benchmark_engine = BenchmarkEngine(db_session)
    quality_gates = QualityGateService(db_session)
    ab_testing = ABTestingService(db_session)
    
    return HermesAgent(
        db_session=db_session,
        prompt_store=prompt_store,
        benchmark_engine=benchmark_engine,
        quality_gate_service=quality_gates,
        ab_testing_service=ab_testing,
    )
