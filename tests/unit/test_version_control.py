"""
Tests for Version Control Service

Unit tests for version control operations.
"""

import pytest

from hermes.services.version_control import VersionControlService


def test_compute_diff():
    """Test computing diff between two versions."""
    old_content = "Line 1\nLine 2\nLine 3"
    new_content = "Line 1\nLine 2 modified\nLine 3"
    
    diff = VersionControlService.compute_diff(old_content, new_content)
    
    assert "Line 2" in diff
    assert "Line 2 modified" in diff
    assert "-Line 2" in diff
    assert "+Line 2 modified" in diff


def test_compute_diff_addition():
    """Test diff with additions."""
    old_content = "Line 1"
    new_content = "Line 1\nLine 2"
    
    diff = VersionControlService.compute_diff(old_content, new_content)
    
    assert "+Line 2" in diff


def test_compute_diff_deletion():
    """Test diff with deletions."""
    old_content = "Line 1\nLine 2"
    new_content = "Line 1"
    
    diff = VersionControlService.compute_diff(old_content, new_content)
    
    assert "-Line 2" in diff


def test_parse_version():
    """Test parsing semantic versions."""
    version = VersionControlService.parse_version("1.2.3")
    
    assert version.major == 1
    assert version.minor == 2
    assert version.patch == 3


def test_increment_version_patch():
    """Test incrementing patch version."""
    new_version = VersionControlService.increment_version("1.0.0", "patch")
    assert new_version == "1.0.1"


def test_increment_version_minor():
    """Test incrementing minor version."""
    new_version = VersionControlService.increment_version("1.0.5", "minor")
    assert new_version == "1.1.0"


def test_increment_version_major():
    """Test incrementing major version."""
    new_version = VersionControlService.increment_version("1.5.3", "major")
    assert new_version == "2.0.0"
