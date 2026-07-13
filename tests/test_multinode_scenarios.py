from __future__ import annotations

import json

import pytest

from scenarios.multinode.config import PcNode, compose_environment, default_nodes, validate_nodes
from scenarios.multinode.runner import ScenarioState, customer_buyer_human, pc1_to_pc2, recovery, run_all, security


def test_default_nodes_have_distinct_ids_ports_and_profiles():
    nodes = default_nodes()
    validate_nodes(nodes)
    env = compose_environment(nodes)
    assert env["PC1_NODE_ID"] == "pc1"
    assert env["PC2_NODE_ID"] == "pc2"
    assert env["PC1_TWIN_ROLE"] == "ifuri-customer"
    assert env["PC2_TWIN_ROLE"] == "ifuri-buyer"
    assert env["PC1_NODE_PORT"] != env["PC2_NODE_PORT"]
    assert env["PC1_PROFILE_DIR"] != env["PC2_PROFILE_DIR"]


def test_duplicate_node_id_is_rejected():
    with pytest.raises(ValueError, match="duplicate node ID"):
        validate_nodes([
            PcNode("pc1", "customer", "ifuri-customer", "pc1", 26080, 28765, "/profiles/pc1"),
            PcNode("pc1", "buyer", "ifuri-buyer", "pc2", 26081, 28766, "/profiles/pc2"),
        ])


def test_pc1_to_pc2_routes_only_to_pc2(tmp_path):
    state = ScenarioState()
    result = pc1_to_pc2(state, tmp_path)
    uris = [event["uri"] for event in state.bus.events]
    pc2_process = [event for event in state.bus.events if event["uri"] == "pc://pc2/task/command/process"]
    wrong_node = [event for event in state.bus.events if event["uri"] == "pc://pc1/task/command/process"]
    assert result["ok"] is True
    assert "mesh://pc1/task/command/send" in uris
    assert len(pc2_process) == 1
    assert wrong_node == []


def test_customer_buyer_human_done_declined_cancel(tmp_path):
    for decision, expected in [("done", "approved"), ("declined", "declined"), ("cancel", "cancelled")]:
        state = ScenarioState()
        result = customer_buyer_human(state, tmp_path, decision)
        assert result["status"] == expected
        assert any(event["uri"] == "human://pc2/task/command/request" for event in state.bus.events)
        if decision == "cancel":
            assert any(event["uri"] == "human://pc2/task/command/cancel" for event in state.bus.events)
        else:
            assert any(event["uri"] == "human://pc2/task/command/resolve" for event in state.bus.events)


def test_recovery_is_retryable_and_idempotent(tmp_path):
    state = ScenarioState()
    result = recovery(state, tmp_path)
    assert result["executions"] == 1
    assert any(event["uri"] == "mesh://pc1/task/query/retryable-error" for event in state.bus.events)
    assert any(event["uri"] == "mesh://pc1/task/query/recovery-complete" for event in state.bus.events)


def test_security_checks_redact_secret(tmp_path):
    state = ScenarioState()
    result = security(state, tmp_path)
    assert result["checks"] == 7
    assert all(event["payload"].get("allowed") is False for event in state.bus.events)
    assert any(event["payload"].get("log") == "[REDACTED]" for event in state.bus.events)


def test_run_all_writes_reports(tmp_path):
    results = run_all(tmp_path)
    assert all(result["status"] == "passed" for result in results)
    assert (tmp_path / "junit.xml").exists()
    assert (tmp_path / "summary.md").exists()
    events = json.loads((tmp_path / "events.json").read_text(encoding="utf-8"))
    assert any(event["uri"] == "customer://ifuri/notification/query/read" for event in events)
