"""Agent skill source paths — auto-discovered from src/skills/.

Each subdirectory containing a SKILL.md is included. To add a new skill,
just create the directory and SKILL.md file — no config changes needed.

Also monkey-patches SkillsMiddleware.before_agent to fix a deepagents 0.5.6
quirk: PrivateStateAttr gives skills_metadata a default [] in the initial
state, causing before_agent's key-existence check to skip loading skills.
"""

from pathlib import Path

from deepagents.middleware.skills import SkillsMiddleware

_SKILLS_ROOT = Path(__file__).resolve().parents[2] / "src" / "skills"

AGENT_SKILL_SOURCES: list[str] = ["/skills/"]

# ---------------------------------------------------------------------------
# Monkey-patch: fix SkillsMiddleware.before_agent skipping load when
# skills_metadata=[] is present in initial state (PrivateStateAttr default).
# ---------------------------------------------------------------------------

_orig_before_agent = SkillsMiddleware.before_agent


def _patched_before_agent(self, state, runtime, config):
    if "skills_metadata" in state and state.get("skills_metadata"):
        return None
    return _orig_before_agent(self, state, runtime, config)


SkillsMiddleware.before_agent = _patched_before_agent
