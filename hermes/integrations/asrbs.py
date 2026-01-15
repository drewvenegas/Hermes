"""
ASRBS Integration

Operational integration with ARIA Self-Recursive Benchmarking System for self-critique.
"""

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
import structlog

from hermes.config import get_settings

settings = get_settings()
logger = structlog.get_logger()


@dataclass
class ImprovementSuggestion:
    """A suggested improvement from ASRBS."""
    
    id: uuid.UUID
    category: str  # clarity, specificity, safety, structure, consistency
    severity: str  # low, medium, high, critical
    description: str
    location: Optional[str] = None  # Line or section reference
    suggested_change: Optional[str] = None
    confidence: float = 0.0
    rationale: str = ""
    estimated_impact: float = 0.0  # Expected score improvement


@dataclass
class SelfCritiqueResult:
    """Result from an ASRBS self-critique run."""
    
    id: uuid.UUID
    prompt_id: uuid.UUID
    prompt_version: str
    overall_assessment: str
    quality_score: float
    suggestions: List[ImprovementSuggestion]
    knowledge_gaps: List[str]
    overconfidence_areas: List[str]
    training_data_needs: List[str]
    executed_at: str
    analysis_depth: str = "standard"  # quick, standard, deep
    model_used: str = "asrbs-v1"


class ASRBSClient:
    """
    Operational client for ASRBS self-critique service.
    
    ASRBS performs meta-cognitive analysis on prompts to identify:
    - Areas for improvement
    - Knowledge gaps
    - Overconfidence risks
    - Training data needs
    """

    def __init__(
        self,
        grpc_url: str = None,
        rest_url: str = None,
        enabled: bool = None,
    ):
        self.grpc_url = grpc_url or settings.asrbs_grpc_url
        self.rest_url = rest_url or "https://asrbs.bravozero.ai/api/v1"
        self.enabled = enabled if enabled is not None else settings.asrbs_enabled
        self._http_client: Optional[httpx.AsyncClient] = None
        
        # Cache for suggestions
        self._suggestion_cache: Dict[str, ImprovementSuggestion] = {}
        
        logger.info(
            "ASRBS client initialized",
            enabled=self.enabled,
            grpc_url=self.grpc_url,
        )

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                base_url=self.rest_url,
                timeout=120.0,
                headers={"Content-Type": "application/json"},
            )
        return self._http_client

    async def analyze_prompt(
        self,
        prompt_content: str,
        prompt_id: uuid.UUID,
        prompt_version: str,
        prompt_type: str,
        depth: str = "standard",
    ) -> SelfCritiqueResult:
        """
        Analyze a prompt using ASRBS self-critique.
        
        Args:
            prompt_content: The prompt content to analyze
            prompt_id: Unique identifier for the prompt
            prompt_version: Semantic version of the prompt
            prompt_type: Type of prompt (agent_system, user_template, etc.)
            depth: Analysis depth (quick, standard, deep)
            
        Returns:
            SelfCritiqueResult with assessment and suggestions
        """
        logger.info(
            "Running ASRBS analysis",
            prompt_id=str(prompt_id),
            version=prompt_version,
            type=prompt_type,
            depth=depth,
        )
        
        if not self.enabled:
            logger.warning("ASRBS disabled, returning simulated result")
            return self._simulate_analysis(prompt_id, prompt_version, prompt_content, depth)
        
        try:
            result = await self._run_analysis_rest(
                prompt_content, prompt_id, prompt_version, prompt_type, depth
            )
        except Exception as e:
            logger.warning(
                "ASRBS analysis failed, using simulation",
                error=str(e),
            )
            result = self._simulate_analysis(prompt_id, prompt_version, prompt_content, depth)
        
        # Cache suggestions for later retrieval
        for suggestion in result.suggestions:
            self._suggestion_cache[str(suggestion.id)] = suggestion
        
        logger.info(
            "ASRBS analysis completed",
            prompt_id=str(prompt_id),
            quality_score=result.quality_score,
            suggestion_count=len(result.suggestions),
        )
        
        return result

    async def _run_analysis_rest(
        self,
        prompt_content: str,
        prompt_id: uuid.UUID,
        prompt_version: str,
        prompt_type: str,
        depth: str,
    ) -> SelfCritiqueResult:
        """Run analysis via REST API."""
        client = await self._get_http_client()
        
        request_body = {
            "prompt_content": prompt_content,
            "prompt_id": str(prompt_id),
            "prompt_version": prompt_version,
            "prompt_type": prompt_type,
            "analysis_depth": depth,
        }
        
        response = await client.post("/analyze", json=request_body)
        response.raise_for_status()
        data = response.json()
        
        return self._parse_analysis_response(data, prompt_id, prompt_version, depth)

    def _parse_analysis_response(
        self,
        data: Dict[str, Any],
        prompt_id: uuid.UUID,
        prompt_version: str,
        depth: str,
    ) -> SelfCritiqueResult:
        """Parse ASRBS API response."""
        suggestions = [
            ImprovementSuggestion(
                id=uuid.UUID(s.get("id", str(uuid.uuid4()))),
                category=s.get("category", "general"),
                severity=s.get("severity", "medium"),
                description=s.get("description", ""),
                location=s.get("location"),
                suggested_change=s.get("suggested_change"),
                confidence=s.get("confidence", 0.8),
                rationale=s.get("rationale", ""),
                estimated_impact=s.get("estimated_impact", 0.0),
            )
            for s in data.get("suggestions", [])
        ]
        
        return SelfCritiqueResult(
            id=uuid.UUID(data.get("id", str(uuid.uuid4()))),
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            overall_assessment=data.get("overall_assessment", ""),
            quality_score=data.get("quality_score", 0.0),
            suggestions=suggestions,
            knowledge_gaps=data.get("knowledge_gaps", []),
            overconfidence_areas=data.get("overconfidence_areas", []),
            training_data_needs=data.get("training_data_needs", []),
            executed_at=data.get("executed_at", datetime.utcnow().isoformat()),
            analysis_depth=depth,
            model_used=data.get("model_used", "asrbs-v1"),
        )

    def _simulate_analysis(
        self,
        prompt_id: uuid.UUID,
        prompt_version: str,
        prompt_content: str,
        depth: str,
    ) -> SelfCritiqueResult:
        """Generate simulated self-critique result."""
        import random
        
        # Analyze prompt structure for more realistic suggestions
        lines = prompt_content.split('\n')
        word_count = len(prompt_content.split())
        has_examples = 'example' in prompt_content.lower()
        has_sections = any(line.startswith('#') or line.startswith('##') for line in lines)
        
        suggestions = []
        
        # Generate context-aware suggestions
        if not has_examples:
            suggestions.append(ImprovementSuggestion(
                id=uuid.uuid4(),
                category="clarity",
                severity="medium",
                description="Consider adding concrete examples to illustrate expected behavior",
                location="General",
                suggested_change="Add 2-3 examples showing input/output patterns",
                confidence=0.88,
                rationale="Examples significantly improve instruction following accuracy",
                estimated_impact=5.0,
            ))
        
        if not has_sections and word_count > 200:
            suggestions.append(ImprovementSuggestion(
                id=uuid.uuid4(),
                category="structure",
                severity="low",
                description="Long prompts benefit from clear section organization",
                location="Overall structure",
                suggested_change="Use markdown headers to organize distinct sections",
                confidence=0.75,
                rationale="Structured prompts improve model comprehension",
                estimated_impact=3.0,
            ))
        
        if 'always' in prompt_content.lower() or 'never' in prompt_content.lower():
            suggestions.append(ImprovementSuggestion(
                id=uuid.uuid4(),
                category="specificity",
                severity="medium",
                description="Absolute terms may need edge case handling",
                location="Constraint definitions",
                suggested_change="Consider adding exceptions or conditions to absolute rules",
                confidence=0.72,
                rationale="Absolute constraints can cause issues in edge cases",
                estimated_impact=4.0,
            ))
        
        # Add standard suggestions based on depth
        if depth in ["standard", "deep"]:
            suggestions.append(ImprovementSuggestion(
                id=uuid.uuid4(),
                category="safety",
                severity="low",
                description="Consider adding explicit safety boundaries",
                location=None,
                suggested_change="Add section on prohibited behaviors",
                confidence=0.65,
                rationale="Explicit safety guidelines improve alignment",
                estimated_impact=2.0,
            ))
        
        # Calculate quality score based on analysis
        base_score = 0.80
        if has_examples:
            base_score += 0.05
        if has_sections:
            base_score += 0.03
        if 100 < word_count < 500:
            base_score += 0.02
        
        quality_score = min(0.95, base_score + random.uniform(-0.05, 0.05))
        
        # Generate knowledge gaps
        knowledge_gaps = []
        if word_count < 50:
            knowledge_gaps.append("Prompt may be too brief to convey full context")
        if not any(term in prompt_content.lower() for term in ['error', 'invalid', 'fail']):
            knowledge_gaps.append("Missing error handling guidance")
        
        # Generate overconfidence areas
        overconfidence_areas = []
        if 'complex' in prompt_content.lower() or 'advanced' in prompt_content.lower():
            overconfidence_areas.append("May overestimate capability on complex nested tasks")
        
        return SelfCritiqueResult(
            id=uuid.uuid4(),
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            overall_assessment=self._generate_assessment(quality_score, suggestions),
            quality_score=quality_score * 100,
            suggestions=suggestions,
            knowledge_gaps=knowledge_gaps or ["Edge case handling may need refinement"],
            overconfidence_areas=overconfidence_areas or ["Standard prompts have typical confidence bounds"],
            training_data_needs=["More domain-specific examples would improve accuracy"],
            executed_at=datetime.utcnow().isoformat(),
            analysis_depth=depth,
            model_used="asrbs-simulation",
        )

    def _generate_assessment(self, score: float, suggestions: List[ImprovementSuggestion]) -> str:
        """Generate overall assessment based on analysis."""
        if score >= 0.9:
            quality = "excellent"
        elif score >= 0.8:
            quality = "good"
        elif score >= 0.7:
            quality = "adequate"
        else:
            quality = "needs improvement"
        
        critical_count = sum(1 for s in suggestions if s.severity == "critical")
        high_count = sum(1 for s in suggestions if s.severity == "high")
        
        if critical_count > 0:
            urgency = f"with {critical_count} critical issue(s) requiring attention"
        elif high_count > 0:
            urgency = f"with {high_count} high-priority improvement(s) suggested"
        else:
            urgency = "with minor improvements suggested"
        
        return f"Prompt quality is {quality} {urgency}."

    async def get_suggestion(self, suggestion_id: str) -> Optional[ImprovementSuggestion]:
        """Get a specific suggestion by ID."""
        if suggestion_id in self._suggestion_cache:
            return self._suggestion_cache[suggestion_id]
        
        # Try to fetch from service
        if self.enabled:
            try:
                client = await self._get_http_client()
                response = await client.get(f"/suggestions/{suggestion_id}")
                response.raise_for_status()
                data = response.json()
                
                suggestion = ImprovementSuggestion(
                    id=uuid.UUID(suggestion_id),
                    category=data.get("category", "general"),
                    severity=data.get("severity", "medium"),
                    description=data.get("description", ""),
                    location=data.get("location"),
                    suggested_change=data.get("suggested_change"),
                    confidence=data.get("confidence", 0.8),
                    rationale=data.get("rationale", ""),
                    estimated_impact=data.get("estimated_impact", 0.0),
                )
                self._suggestion_cache[suggestion_id] = suggestion
                return suggestion
            except Exception as e:
                logger.warning(
                    "Failed to fetch suggestion",
                    suggestion_id=suggestion_id,
                    error=str(e),
                )
        
        return None

    async def apply_suggestion(
        self,
        prompt_content: str,
        suggestion: ImprovementSuggestion,
    ) -> str:
        """
        Apply a suggestion to prompt content automatically.
        
        Uses ASRBS to generate the modified content based on the suggestion.
        """
        logger.info(
            "Applying suggestion",
            suggestion_id=str(suggestion.id),
            category=suggestion.category,
        )
        
        if not self.enabled or not suggestion.suggested_change:
            # Return original if ASRBS unavailable or no specific change
            return prompt_content
        
        try:
            client = await self._get_http_client()
            response = await client.post(
                "/apply-suggestion",
                json={
                    "prompt_content": prompt_content,
                    "suggestion_id": str(suggestion.id),
                    "suggestion": {
                        "category": suggestion.category,
                        "description": suggestion.description,
                        "suggested_change": suggestion.suggested_change,
                        "location": suggestion.location,
                    },
                },
            )
            response.raise_for_status()
            data = response.json()
            return data.get("modified_content", prompt_content)
        except Exception as e:
            logger.warning(
                "Failed to apply suggestion via ASRBS",
                suggestion_id=str(suggestion.id),
                error=str(e),
            )
            return prompt_content

    async def get_improvement_history(
        self,
        prompt_id: uuid.UUID,
        limit: int = 10,
    ) -> List[SelfCritiqueResult]:
        """Get history of self-critique analyses for a prompt."""
        if not self.enabled:
            return []
        
        try:
            client = await self._get_http_client()
            response = await client.get(
                f"/history/{prompt_id}",
                params={"limit": limit},
            )
            response.raise_for_status()
            data = response.json()
            
            return [
                self._parse_analysis_response(item, prompt_id, item.get("prompt_version", ""), "standard")
                for item in data.get("analyses", [])
            ]
        except Exception as e:
            logger.warning(
                "Failed to fetch improvement history",
                prompt_id=str(prompt_id),
                error=str(e),
            )
            return []

    async def close(self):
        """Close HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None


# Singleton instance
_asrbs_client: Optional[ASRBSClient] = None


def get_asrbs_client() -> ASRBSClient:
    """Get the ASRBS client singleton."""
    global _asrbs_client
    if _asrbs_client is None:
        _asrbs_client = ASRBSClient()
    return _asrbs_client


async def shutdown_asrbs_client():
    """Shutdown the ASRBS client."""
    global _asrbs_client
    if _asrbs_client:
        await _asrbs_client.close()
        _asrbs_client = None
