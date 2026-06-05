"""
GuardSpine Package.

GS-009/010/011: Security guards for configuration, prompts, and hooks.

Components:
- ConfigGuard: Configuration file security (GS-009)
- PromptGuard: Prompt injection detection (GS-010)
- HookGuard: Shell script security (GS-011)
"""

from .configguard import (
    ConfigGuard,
    ConfigViolation,
    ConfigScanResult,
    ConfigType,
)

from .promptguard import (
    PromptGuard,
    PromptViolation,
    PromptScanResult,
    InjectionType,
)

from .hookguard import (
    HookGuard,
    HookViolation,
    HookScanResult,
    ShellType,
)

__all__ = [
    # ConfigGuard (GS-009)
    "ConfigGuard",
    "ConfigViolation",
    "ConfigScanResult",
    "ConfigType",
    # PromptGuard (GS-010)
    "PromptGuard",
    "PromptViolation",
    "PromptScanResult",
    "InjectionType",
    # HookGuard (GS-011)
    "HookGuard",
    "HookViolation",
    "HookScanResult",
    "ShellType",
]
