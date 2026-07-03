"""Test that SERVICE_PROPS includes 'aliases' for alias support."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_service_props_includes_aliases():
    """SERVICE_PROPS must contain 'aliases' for Neo4j alias support."""
    from app.schema import SERVICE_PROPS
    assert "aliases" in SERVICE_PROPS, f"aliases not in SERVICE_PROPS: {SERVICE_PROPS}"


def test_allowed_props_service_includes_aliases():
    """ALLOWED_PROPS['Service'] must contain 'aliases'."""
    from app.schema import ALLOWED_PROPS
    assert "aliases" in ALLOWED_PROPS["Service"], \
        f"aliases not in ALLOWED_PROPS Service: {ALLOWED_PROPS['Service']}"
