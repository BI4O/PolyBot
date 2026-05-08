"""Deep Agent filesystem backend configuration.

Routes virtual paths to local storage:
  /skills/ → src/skills/  (read/write via FilesystemBackend)
  /         → ephemeral StateBackend (scratch space)
"""

from pathlib import Path

from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend

_SKILLS_ROOT = str(Path(__file__).resolve().parents[2] / "src" / "skills")

AGENT_BACKEND = CompositeBackend(
    default=StateBackend(),
    routes={
        "/skills/": FilesystemBackend(
            root_dir=_SKILLS_ROOT,
            virtual_mode=True,
        ),
    },
)
