#!/usr/bin/env python3
"""
Seed ARIA Agents Script

Seeds all ARIA agent prompts from the Nursery into Hermes.
This script imports the system prompts for all 32+ ARIA agents.
"""

import asyncio
import os
import sys
import uuid
from pathlib import Path
from typing import Dict, List, Optional

import yaml
import structlog

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from hermes.services.database import get_db_session, init_db, close_db
from hermes.services.prompt_store import PromptStoreService
from hermes.schemas.prompt import PromptCreate
from hermes.models.prompt import PromptType

logger = structlog.get_logger()

# ARIA Agent Definitions
# Organized by category as per the system architecture
ARIA_AGENTS = {
    # Executive Layer
    "executive": [
        {
            "slug": "aria",
            "name": "ARIA",
            "description": "Primary executive agent - master orchestrator of the Bravo Zero cognitive architecture",
            "category": "executive",
        },
        {
            "slug": "constitution",
            "name": "Constitution",
            "description": "Core values and ethical guidelines enforcer for all ARIA subsystems",
            "category": "executive",
        },
        {
            "slug": "meta-coordinator",
            "name": "Meta Coordinator",
            "description": "High-level task allocation and system-wide coordination",
            "category": "executive",
        },
        {
            "slug": "wisdom",
            "name": "Wisdom",
            "description": "Strategic advisor providing long-term perspective and accumulated knowledge",
            "category": "executive",
        },
    ],
    
    # Orchestration Layer
    "orchestration": [
        {
            "slug": "conductor",
            "name": "Conductor",
            "description": "Real-time workflow orchestration and task sequencing",
            "category": "orchestration",
        },
        {
            "slug": "project-manager",
            "name": "Project Manager",
            "description": "Multi-project coordination, resource allocation, and timeline management",
            "category": "orchestration",
        },
    ],
    
    # Specialist Agents
    "specialists": [
        {
            "slug": "software-engineer",
            "name": "Software Engineer",
            "description": "Expert coding agent for software development tasks",
            "category": "specialists",
        },
        {
            "slug": "researcher",
            "name": "Researcher",
            "description": "Deep research and information synthesis agent",
            "category": "specialists",
        },
        {
            "slug": "data-analyst",
            "name": "Data Analyst",
            "description": "Data processing, analysis, and visualization specialist",
            "category": "specialists",
        },
        {
            "slug": "legal",
            "name": "Legal",
            "description": "Legal analysis, compliance checking, and contract review",
            "category": "specialists",
        },
        {
            "slug": "creative",
            "name": "Creative",
            "description": "Creative content generation and ideation",
            "category": "specialists",
        },
        {
            "slug": "security-analyst",
            "name": "Security Analyst",
            "description": "Security assessment and threat analysis",
            "category": "specialists",
        },
        {
            "slug": "ux-designer",
            "name": "UX Designer",
            "description": "User experience design and interface optimization",
            "category": "specialists",
        },
        {
            "slug": "technical-writer",
            "name": "Technical Writer",
            "description": "Documentation and technical content creation",
            "category": "specialists",
        },
    ],
    
    # Subsystem Agents
    "subsystems": [
        {
            "slug": "joshua",
            "name": "JOSHUA",
            "description": "Game-theoretic reasoning and strategic analysis subsystem",
            "category": "subsystems",
        },
        {
            "slug": "sdsm",
            "name": "SDSM",
            "description": "Semantic Data & State Manager - manages semantic memory and state",
            "category": "subsystems",
        },
        {
            "slug": "carousel",
            "name": "Carousel",
            "description": "Continuous context management and working memory optimization",
            "category": "subsystems",
        },
        {
            "slug": "athena",
            "name": "Athena",
            "description": "Strategic planning and goal decomposition engine",
            "category": "subsystems",
        },
        {
            "slug": "beeper",
            "name": "Beeper",
            "description": "Notification and messaging coordination system",
            "category": "subsystems",
        },
        {
            "slug": "forge",
            "name": "Forge",
            "description": "Code generation and refactoring toolkit",
            "category": "subsystems",
        },
        {
            "slug": "hydra",
            "name": "Hydra",
            "description": "Multi-headed execution environment for parallel task processing",
            "category": "subsystems",
        },
        {
            "slug": "odyssey",
            "name": "Odyssey",
            "description": "Long-term planning and journey orchestration",
            "category": "subsystems",
        },
        {
            "slug": "hermes",
            "name": "Hermes",
            "description": "Prompt engineering and optimization platform agent",
            "category": "subsystems",
        },
        {
            "slug": "logos",
            "name": "Logos",
            "description": "IDE integration and developer experience agent",
            "category": "subsystems",
        },
        {
            "slug": "ate",
            "name": "ATE",
            "description": "ARIA Testing & Evolution - benchmark and evaluation system",
            "category": "subsystems",
        },
        {
            "slug": "asrbs",
            "name": "ASRBS",
            "description": "ARIA Self-Recursive Benchmarking System - self-improvement engine",
            "category": "subsystems",
        },
        {
            "slug": "persona",
            "name": "PERSONA",
            "description": "Identity and access management for zero-trust security",
            "category": "subsystems",
        },
    ],
    
    # D3N Model Agents
    "d3n": [
        {
            "slug": "paperclip-01",
            "name": "Paperclip-01",
            "description": "BMU D3N - Base Memory Unit for context storage",
            "category": "d3n",
        },
        {
            "slug": "yap-01",
            "name": "Yap-01",
            "description": "Chatterbox TTS D3N - Text-to-speech synthesis",
            "category": "d3n",
        },
        {
            "slug": "vjepa2-01",
            "name": "VJEPA2-01",
            "description": "Vision D3N - Visual understanding and processing",
            "category": "d3n",
        },
        {
            "slug": "whisper-01",
            "name": "Whisper-01",
            "description": "Speech-to-text transcription D3N",
            "category": "d3n",
        },
        {
            "slug": "codex-01",
            "name": "Codex-01",
            "description": "Code generation and understanding D3N",
            "category": "d3n",
        },
        {
            "slug": "embed-01",
            "name": "Embed-01",
            "description": "Embedding generation D3N",
            "category": "d3n",
        },
        {
            "slug": "judge-01",
            "name": "Judge-01",
            "description": "Quality assessment and evaluation D3N",
            "category": "d3n",
        },
        {
            "slug": "json-01",
            "name": "JSON-01",
            "description": "Structured output generation D3N",
            "category": "d3n",
        },
        {
            "slug": "sage-01",
            "name": "Sage-01",
            "description": "Reasoning and knowledge synthesis D3N",
            "category": "d3n",
        },
        {
            "slug": "document-01",
            "name": "Document-01",
            "description": "Document processing and extraction D3N",
            "category": "d3n",
        },
        {
            "slug": "sum-01",
            "name": "Sum-01",
            "description": "Summarization D3N",
            "category": "d3n",
        },
    ],
}


def generate_default_system_prompt(agent: Dict) -> str:
    """Generate a default system prompt for an agent."""
    return f"""# {agent['name']} System Prompt

You are {agent['name']}, a specialized agent in the Bravo Zero cognitive architecture.

## Role
{agent['description']}

## Core Responsibilities
- Fulfill your designated role within the ARIA multi-agent system
- Coordinate with other agents through proper protocols
- Maintain high quality standards in all outputs
- Report issues and uncertainties appropriately

## Behavioral Guidelines
1. Always identify yourself when communicating with other agents
2. Follow the ARIA Constitution and ethical guidelines
3. Use structured outputs when appropriate
4. Provide clear reasoning for decisions
5. Escalate issues that exceed your capabilities

## Communication Protocol
- Use clear, precise language
- Include relevant context in responses
- Acknowledge task completion or failure explicitly
- Request clarification when instructions are ambiguous

## Integration Points
- Coordinate with SDSM for memory operations
- Use PERSONA for identity verification
- Report metrics to ATE for benchmarking
- Log significant events to Beeper for notifications
"""


async def seed_agents(
    nursery_path: Optional[Path] = None,
    force: bool = False,
    dry_run: bool = False,
) -> Dict[str, int]:
    """
    Seed all ARIA agents into Hermes.
    
    Args:
        nursery_path: Path to ARIA Nursery (optional, uses defaults if not provided)
        force: Overwrite existing prompts
        dry_run: Validate without saving
        
    Returns:
        Dict with counts of created, updated, skipped, failed
    """
    results = {
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
        "agents": [],
    }
    
    # System owner for agent prompts
    system_owner = uuid.UUID("00000000-0000-0000-0000-000000000001")
    
    await init_db()
    
    try:
        async with get_db_session() as db:
            store = PromptStoreService(db)
            
            # Process all agent categories
            for category, agents in ARIA_AGENTS.items():
                logger.info(f"Processing {category} agents ({len(agents)} total)")
                
                for agent in agents:
                    try:
                        # Check if prompt exists
                        existing = await store.get_by_slug(agent["slug"])
                        
                        # Try to load from nursery if available
                        content = None
                        if nursery_path:
                            nursery_file = nursery_path / f"{agent['slug']}.md"
                            if nursery_file.exists():
                                content = nursery_file.read_text()
                                logger.info(f"Loaded {agent['slug']} from nursery")
                        
                        # Use default if no nursery content
                        if not content:
                            content = generate_default_system_prompt(agent)
                        
                        if existing and not force:
                            results["skipped"] += 1
                            logger.info(f"Skipped {agent['slug']} (exists)")
                            continue
                        
                        if dry_run:
                            action = "would_update" if existing else "would_create"
                            logger.info(f"[DRY RUN] {action} {agent['slug']}")
                            results["created" if not existing else "updated"] += 1
                            continue
                        
                        # Create or update
                        prompt_data = PromptCreate(
                            name=agent["name"],
                            slug=agent["slug"],
                            description=agent["description"],
                            type=PromptType.AGENT_SYSTEM,
                            category=agent["category"],
                            content=content,
                            metadata={
                                "aria_agent": True,
                                "category": category,
                                "auto_seeded": True,
                            },
                        )
                        
                        if existing:
                            from hermes.schemas.prompt import PromptUpdate
                            update_data = PromptUpdate(
                                content=content,
                                name=agent["name"],
                                description=agent["description"],
                            )
                            await store.update(existing.id, update_data, change_summary="Auto-seeded from ARIA Nursery")
                            results["updated"] += 1
                            logger.info(f"Updated {agent['slug']}")
                        else:
                            await store.create(prompt_data, owner_id=system_owner)
                            results["created"] += 1
                            logger.info(f"Created {agent['slug']}")
                        
                        results["agents"].append({
                            "slug": agent["slug"],
                            "name": agent["name"],
                            "action": "updated" if existing else "created",
                        })
                        
                    except Exception as e:
                        results["failed"] += 1
                        logger.error(f"Failed to seed {agent['slug']}: {e}")
            
            if not dry_run:
                await db.commit()
                logger.info("Database changes committed")
    
    finally:
        await close_db()
    
    return results


async def main():
    """Main entry point for the script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Seed ARIA agents into Hermes")
    parser.add_argument(
        "--nursery",
        type=Path,
        help="Path to ARIA Nursery directory",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing prompts",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate without saving",
    )
    
    args = parser.parse_args()
    
    # Try default nursery path if not provided
    nursery_path = args.nursery
    if not nursery_path:
        default_path = Path(__file__).parent.parent.parent / "ARIA" / "Nursery"
        if default_path.exists():
            nursery_path = default_path
            logger.info(f"Using default nursery path: {nursery_path}")
    
    logger.info("Starting ARIA agent seeding", force=args.force, dry_run=args.dry_run)
    
    results = await seed_agents(
        nursery_path=nursery_path,
        force=args.force,
        dry_run=args.dry_run,
    )
    
    # Print summary
    print("\n" + "=" * 50)
    print("ARIA Agent Seeding Complete")
    print("=" * 50)
    print(f"Created:  {results['created']}")
    print(f"Updated:  {results['updated']}")
    print(f"Skipped:  {results['skipped']}")
    print(f"Failed:   {results['failed']}")
    print(f"Total:    {sum(len(agents) for agents in ARIA_AGENTS.values())}")
    print("=" * 50)
    
    if results["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
