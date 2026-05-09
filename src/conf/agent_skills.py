"""Agent skill source paths — auto-discovered from src/skills/.

Each subdirectory containing a SKILL.md is included. To add a new skill,
just create the directory and SKILL.md file — no config changes needed.
"""

from pathlib import Path

_SKILLS_ROOT = Path(__file__).resolve().parents[2] / "src" / "skills"

AGENT_SKILL_SOURCES: list[str] = ["/skills/"]
