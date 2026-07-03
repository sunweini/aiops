"""Test that load-topology writes aliases to Neo4j Service nodes."""
import pytest
import importlib.util
import os
import sys
from unittest.mock import MagicMock

# Load load-topology.py (hyphenated filename requires importlib)
_lt_path = os.path.join(os.path.dirname(__file__), "..", "scripts", "load-topology.py")
_lt_path = os.path.abspath(_lt_path)
spec = importlib.util.spec_from_file_location("load_topology", _lt_path)
lt_module = importlib.util.module_from_spec(spec)
sys.modules["load_topology"] = lt_module
spec.loader.exec_module(lt_module)


def test_load_topology_writes_aliases():
    """When service has aliases in YAML, load_topology SETs aliases on Service node."""
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__ = lambda s: mock_session
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

    # Track all session.run calls
    run_calls = []
    mock_session.run.side_effect = lambda *args, **kwargs: run_calls.append((args, kwargs)) or MagicMock()

    import unittest.mock as mock
    with mock.patch.object(lt_module, 'get_driver', return_value=mock_driver):
        with mock.patch('app.schema.validate_topology', return_value=[]):
            with mock.patch('app.schema.validate_cross_refs', return_value=[]):
                # Minimal topology with aliases
                test_data = {
                    "services": [
                        {
                            "id": "svc_test",
                            "name": "test-service",
                            "aliases": ["test", "测试服务"],
                        }
                    ],
                    "hosts": [],
                }
                with mock.patch('builtins.open', mock.mock_open(read_data='dummy')):
                    with mock.patch('yaml.safe_load', return_value=test_data):
                        lt_module.load_topology('fake.yml')

    # Check that session.run was called with aliases parameter
    alias_calls = [c for c in run_calls
                   if len(c) > 0 and 'aliases' in str(c)]
    assert len(alias_calls) > 0, f"No calls contained 'aliases': {run_calls[:5]}"


def test_load_topology_aliases_in_cypher_query():
    """Verify the Cypher query includes svc.aliases = $aliases."""
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__ = lambda s: mock_session
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

    run_calls = []
    mock_session.run.side_effect = lambda *args, **kwargs: run_calls.append((args, kwargs)) or MagicMock()

    import unittest.mock as mock
    with mock.patch.object(lt_module, 'get_driver', return_value=mock_driver):
        with mock.patch('app.schema.validate_topology', return_value=[]):
            with mock.patch('app.schema.validate_cross_refs', return_value=[]):
                test_data = {
                    "services": [
                        {
                            "id": "svc_test",
                            "name": "test-service",
                            "aliases": ["test", "测试服务"],
                        }
                    ],
                    "hosts": [],
                }
                with mock.patch('builtins.open', mock.mock_open(read_data='dummy')):
                    with mock.patch('yaml.safe_load', return_value=test_data):
                        lt_module.load_topology('fake.yml')

    # Find the MERGE Service call and verify it includes aliases in both query and params
    service_merge_calls = [
        c for c in run_calls
        if len(c[0]) > 0 and 'MERGE' in str(c[0][0]) and 'Service' in str(c[0][0])
    ]
    assert len(service_merge_calls) > 0, f"No MERGE Service calls found in: {[c[0][0][:60] for c in run_calls if c[0]]}"

    query, kwargs = service_merge_calls[0]
    assert 'svc.aliases' in query[0], f"Cypher query missing svc.aliases: {query[0]}"
    assert 'aliases' in kwargs, f"kwargs missing 'aliases': {kwargs}"
    assert kwargs['aliases'] == ["test", "测试服务"], f"aliases value wrong: {kwargs['aliases']}"
