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


def test_topology_schema_includes_aliases():
    """TOPOLOGY_SCHEMA service properties must include 'aliases' array."""
    from app.schema import TOPOLOGY_SCHEMA
    service_props = TOPOLOGY_SCHEMA["properties"]["services"]["items"]["properties"]
    assert "aliases" in service_props, \
        f"aliases not in TOPOLOGY_SCHEMA service properties: {list(service_props.keys())}"
    assert service_props["aliases"]["type"] == "array"
    assert service_props["aliases"]["items"]["type"] == "string"
