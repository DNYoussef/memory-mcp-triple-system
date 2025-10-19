"""
Unit tests for Mode Profile.

Tests mode configuration, validation, and predefined profiles.
"""

import pytest
from src.modes.mode_profile import (
    ModeProfile,
    EXECUTION,
    PLANNING,
    BRAINSTORMING,
    get_profile
)


class TestModeProfileCreation:
    """Test suite for mode profile creation and validation."""

    def test_mode_profile_creation(self):
        """Test creating a custom mode profile."""
        profile = ModeProfile(
            name="custom",
            core_size=10,
            extended_size=20,
            verification_enabled=True,
            constraints_enabled=True,
            latency_budget_ms=1000,
            token_budget=15000,
            randomness=0.05
        )

        assert profile.name == "custom"
        assert profile.core_size == 10
        assert profile.extended_size == 20
        assert profile.total_size == 30
        assert profile.verification_enabled is True
        assert profile.constraints_enabled is True
        assert profile.latency_budget_ms == 1000
        assert profile.token_budget == 15000
        assert profile.randomness == 0.05

    def test_mode_profile_validation_negative_core(self):
        """Test validation rejects negative core_size."""
        with pytest.raises(ValueError, match="core_size must be ≥0"):
            ModeProfile(
                name="invalid",
                core_size=-1,
                extended_size=10,
                verification_enabled=True,
                constraints_enabled=True,
                latency_budget_ms=1000,
                token_budget=10000,
                randomness=0.0
            )

    def test_mode_profile_validation_negative_extended(self):
        """Test validation rejects negative extended_size."""
        with pytest.raises(ValueError, match="extended_size must be ≥0"):
            ModeProfile(
                name="invalid",
                core_size=5,
                extended_size=-5,
                verification_enabled=True,
                constraints_enabled=True,
                latency_budget_ms=1000,
                token_budget=10000,
                randomness=0.0
            )

    def test_mode_profile_validation_invalid_latency(self):
        """Test validation rejects non-positive latency_budget_ms."""
        with pytest.raises(ValueError, match="latency_budget_ms must be >0"):
            ModeProfile(
                name="invalid",
                core_size=5,
                extended_size=10,
                verification_enabled=True,
                constraints_enabled=True,
                latency_budget_ms=0,
                token_budget=10000,
                randomness=0.0
            )

    def test_mode_profile_validation_invalid_token_budget(self):
        """Test validation rejects non-positive token_budget."""
        with pytest.raises(ValueError, match="token_budget must be >0"):
            ModeProfile(
                name="invalid",
                core_size=5,
                extended_size=10,
                verification_enabled=True,
                constraints_enabled=True,
                latency_budget_ms=1000,
                token_budget=-100,
                randomness=0.0
            )

    def test_mode_profile_validation_randomness_out_of_range(self):
        """Test validation rejects randomness outside [0.0, 1.0]."""
        with pytest.raises(ValueError, match="randomness must be in"):
            ModeProfile(
                name="invalid",
                core_size=5,
                extended_size=10,
                verification_enabled=True,
                constraints_enabled=True,
                latency_budget_ms=1000,
                token_budget=10000,
                randomness=1.5
            )


class TestPredefinedProfiles:
    """Test suite for predefined mode profiles."""

    def test_execution_mode_profile(self):
        """Test execution mode profile configuration."""
        assert EXECUTION.name == "execution"
        assert EXECUTION.core_size == 5
        assert EXECUTION.extended_size == 0  # Precision only
        assert EXECUTION.total_size == 5
        assert EXECUTION.verification_enabled is True
        assert EXECUTION.constraints_enabled is True
        assert EXECUTION.latency_budget_ms == 500  # Fast
        assert EXECUTION.token_budget == 5000  # Minimal
        assert EXECUTION.randomness == 0.0  # No randomness

    def test_planning_mode_profile(self):
        """Test planning mode profile configuration."""
        assert PLANNING.name == "planning"
        assert PLANNING.core_size == 5
        assert PLANNING.extended_size == 15  # Balanced
        assert PLANNING.total_size == 20
        assert PLANNING.verification_enabled is True
        assert PLANNING.constraints_enabled is True
        assert PLANNING.latency_budget_ms == 1000  # Medium
        assert PLANNING.token_budget == 10000  # Balanced
        assert PLANNING.randomness == 0.05  # 5% random

    def test_brainstorming_mode_profile(self):
        """Test brainstorming mode profile configuration."""
        assert BRAINSTORMING.name == "brainstorming"
        assert BRAINSTORMING.core_size == 5
        assert BRAINSTORMING.extended_size == 25  # High recall
        assert BRAINSTORMING.total_size == 30
        assert BRAINSTORMING.verification_enabled is False  # Creative
        assert BRAINSTORMING.constraints_enabled is False  # Creative
        assert BRAINSTORMING.latency_budget_ms == 2000  # Slower OK
        assert BRAINSTORMING.token_budget == 20000  # Large
        assert BRAINSTORMING.randomness == 0.10  # 10% random

    def test_get_profile_execution(self):
        """Test getting execution profile by name."""
        profile = get_profile("execution")
        assert profile == EXECUTION

    def test_get_profile_planning(self):
        """Test getting planning profile by name."""
        profile = get_profile("planning")
        assert profile == PLANNING

    def test_get_profile_brainstorming(self):
        """Test getting brainstorming profile by name."""
        profile = get_profile("brainstorming")
        assert profile == BRAINSTORMING

    def test_get_profile_unknown(self):
        """Test get_profile raises error for unknown mode."""
        with pytest.raises(ValueError, match="Unknown mode: invalid"):
            get_profile("invalid")
