"""Puente hacia `pipeline/` (CRISP-DM): el backend no procesa datos, solo sirve
lo que el pipeline ya integró, limpió, modeló y evaluó."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pipeline.despliegue import PipelineResult, load_or_build  # noqa: E402
from pipeline.despliegue import variable_catalog as _variable_catalog  # noqa: E402

Dataset = PipelineResult


def load_dataset() -> Dataset:
    return load_or_build()


def variable_catalog() -> list[dict]:
    return _variable_catalog()
