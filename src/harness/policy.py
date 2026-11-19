from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from .profiles import (
    DEFAULT_ASYNC_SECONDS,
    DEFAULT_OBJECT_MAX_BYTES,
    DEFAULT_PROFILE,
    PROFILES,
    canonical_profile,
)


class PolicyError(ValueError):
    def __init__(self, message: str, code: str = "invalid-config") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Policy:
    database_object_max_bytes: int
    estimated_duration_max_seconds: int | float


def _object(value: Any, name: str) -> dict:
    if not isinstance(value, dict):
        raise PolicyError(f"{name} must be a JSON object")
    return value


def parse_profile(value: Any, override: str | None = None) -> str:
    config = _object(value, "config.json")
    profile = override if override is not None else config.get("profile", DEFAULT_PROFILE)
    if isinstance(profile, str):
        profile = canonical_profile(profile)
    if not isinstance(profile, str) or profile not in PROFILES:
        raise PolicyError(f"unknown project profile: {profile!r}; choose from {', '.join(PROFILES)}")
    return profile


def parse_policy(value: Any) -> Policy:
    config = _object(value, "config.json")
    constraints = _object(config.get("constraints", {}), "constraints")
    storage = _object(constraints.get("storage", {}), "constraints.storage")
    asynchronous = _object(constraints.get("asynchronous_work", {}), "constraints.asynchronous_work")

    size = storage.get("database_object_max_bytes", DEFAULT_OBJECT_MAX_BYTES)
    duration = asynchronous.get("estimated_duration_max_seconds", DEFAULT_ASYNC_SECONDS)
    if type(size) is not int or size <= 0:
        raise PolicyError("database_object_max_bytes must be a positive integer", "invalid-threshold")
    if type(duration) not in (int, float) or duration <= 0 or (type(duration) is float and not math.isfinite(duration)):
        raise PolicyError("estimated_duration_max_seconds must be a positive finite number", "invalid-threshold")
    return Policy(size, duration)
