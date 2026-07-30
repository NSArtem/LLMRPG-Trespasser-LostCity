"""Deterministic, model-independent module extraction pipeline."""

from .errors import ExtractorError
from .scene import resolve_scene

__all__ = ["ExtractorError", "resolve_scene"]
__version__ = "2.0.0"
