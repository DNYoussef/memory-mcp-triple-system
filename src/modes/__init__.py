"""
Mode-aware context module.

Provides mode profiles and detection for execution, planning, and brainstorming modes.
"""
from .mode_profile import ModeProfile, EXECUTION, PLANNING, BRAINSTORMING, get_profile
from .mode_detector import ModeDetector

__all__ = [
    "ModeProfile",
    "EXECUTION",
    "PLANNING",
    "BRAINSTORMING",
    "get_profile",
    "ModeDetector"
]
