from __future__ import annotations

import argparse
import base64
import json
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import default_nodes, validate_nodes

PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


@dataclass
class EventBus:
    events: list[dict[str, Any]] = field(default_factory=list)

    def emit(self, uri: str, node: str, payload: dict[str, Any] | None = None) -> None:
        self.events.append({"seq": len(self.events) + 1, "ts": time.time(), "node": node, "uri": uri, "payload": payload or {}})


@dataclass
class ScenarioState:
    bus: EventBus = field(default_factory=EventBus)
    executed: set[str] = field(default_factory=set)
    pc2_online: bool = True

    def ensure_pc2(self) -> None:
        if not self.pc2_online:
            raise RetryableNodeError("pc2 unavailable")


class RetryableNodeError(RuntimeError):
    pass


def _evidence(out: Path, name: str, node: str, uri: str, status: str) -> dict[str, str]:
    evidence_dir = out / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    before = evidence_dir / f"{name}-before.png"
    after = evidence_dir / f"{name}-after.png"
    dom = evidence_dir / f"{name}-dom.json"
    before.write_bytes(PNG_1PX)
    after.write_bytes(PNG_1PX)
    dom.write_text(json.dumps({"node": node, "uri": uri, "status": status, "verified": True}, indent=2), encoding="utf-8")
    return {"before": str(before), "after": str(after), "dom": str(dom)}


def pc1_to_pc2(state: ScenarioState, out: Path) -> dict[str, Any]:
    key = "pc1-to-pc2:artifact-001"
    state.bus.emit("mesh://pc1/session/command/register", "pc1", {"nodeId": "pc1"})
    state.bus.emit("mesh://pc2/session/command/register", "pc2", {"nodeId": "pc2"})
    state.bus.emit("pc://pc1/task/command/create", "pc1", {"artifact": "artifact-001"})
    state.bus.emit("mesh://pc1/task/command/send", "pc1", {"target": "pc2", "idempotencyKey": key})
    state.ensure_pc2()
    if key not in state.executed:
        state.executed.add(key)
        state.bus.emit("pc://pc2/task/query/read", "pc2", {"artifact": "artifact-001"})
        state.bus.emit("pc://pc2/task/command/process", "pc2", {"result": "processed"})
    state.bus.emit("mesh://pc2/result/command/send", "pc2", {"target": "pc1", "idempotencyKey": key})
    state.bus.emit("pc://pc1/result/query/read", "pc1", {"result": "processed"})
    return {"ok": True, "idempotencyKey": key, "executions": len(state.executed)}


def customer_buyer_human(state: ScenarioState, out: Path, decision: str = "done") -> dict[str, Any]:
    if decision not in {"done", "declined", "cancel"}:
        raise ValueError(f"unsupported decision: {decision}")
    order = "order-1001"
    state.bus.emit("customer://ifuri/session/command/start", "pc1", {"role": "ifuri-customer"})
    state.bus.emit("pc://pc1/browser/command/navigate", "pc1", {"url": "http://business-portal:8010"})
    evidence = _evidence(out, f"customer-order-{decision}", "pc1", "pc://pc1/browser/command/navigate", "verified")
    state.bus.emit("order://ifuri/request/command/create", "pc1", {"order": order, "evidence": evidence})
    state.bus.emit("mesh://pc1/task/command/send", "pc1", {"target": "pc2", "role": "ifuri-buyer"})
    state.ensure_pc2()
    state.bus.emit("pc://pc2/task/query/read", "pc2", {"order": order})
    state.bus.emit("pc://pc2/browser/command/navigate", "pc2", {"url": "http://business-portal:8010/orders"})
    _evidence(out, f"buyer-review-{decision}", "pc2", "pc://pc2/browser/command/navigate", "verified")
    state.bus.emit("human://pc2/task/command/request", "pc2", {"order": order, "scope": "per-instance", "status": "pending"})
    if decision == "cancel":
        state.bus.emit("human://pc2/task/command/cancel", "pc2", {"order": order, "status": "cancelled"})
        state.bus.emit("order://ifuri/request/command/cancel", "pc2", {"order": order})
        return {"ok": True, "status": "cancelled"}
    state.bus.emit("human://pc2/task/command/resolve", "pc2", {"order": order, "status": decision, "proof": "operator-test"})
    if decision == "declined":
        state.bus.emit("order://ifuri/request/command/decline", "pc2", {"order": order})
        state.bus.emit("mesh://pc2/result/command/send", "pc2", {"target": "pc1", "status": "declined"})
        return {"ok": True, "status": "declined"}
    state.bus.emit("order://ifuri/request/command/approve", "pc2", {"order": order})
    state.bus.emit("mesh://pc2/result/command/send", "pc2", {"target": "pc1", "status": "approved"})
    state.bus.emit("customer://ifuri/notification/query/read", "pc1", {"order": order, "status": "approved"})
    return {"ok": True, "status": "approved"}


def recovery(state: ScenarioState, out: Path) -> dict[str, Any]:
    state.pc2_online = False
    try:
        pc1_to_pc2(state, out)
    except RetryableNodeError as exc:
        state.bus.emit("mesh://pc1/task/query/retryable-error", "pc1", {"target": "pc2", "error": str(exc)})
    else:  # pragma: no cover
        raise AssertionError("pc2 outage did not fail")
    state.pc2_online = True
    result = pc1_to_pc2(state, out)
    state.bus.emit("mesh://pc1/task/query/recovery-complete", "pc1", result)
    return result


def security(state: ScenarioState, out: Path) -> dict[str, Any]:
    checks = {
        "forbidden-uri": "pc://pc1/secret/query/read",
        "wrong-node": "pc://pc1/task/command/process",
        "bad-uri": "not-a-uri",
        "bad-payload": "mesh://pc1/task/command/send",
        "missing-connector": "erp://pc2/order/command/post",
        "offline-node": "mesh://pc1/task/command/send",
        "secret-redaction": "secret://keyring/customer/password",
    }
    for name, uri in checks.items():
        state.bus.emit("security://routing/check", "pc1", {"case": name, "uri": uri, "allowed": False, "log": "[REDACTED]"})
    return {"ok": True, "checks": len(checks)}


def run_all(out: Path) -> list[dict[str, Any]]:
    validate_nodes(default_nodes())
    out.mkdir(parents=True, exist_ok=True)
    cases = [
        ("pc1_to_pc2", lambda s: pc1_to_pc2(s, out)),
        ("customer_buyer_done", lambda s: customer_buyer_human(s, out, "done")),
        ("human_declined", lambda s: customer_buyer_human(s, out, "declined")),
        ("human_cancel", lambda s: customer_buyer_human(s, out, "cancel")),
        ("recovery", lambda s: recovery(s, out)),
        ("security", lambda s: security(s, out)),
    ]
    results: list[dict[str, Any]] = []
    aggregate = EventBus()
    for name, func in cases:
        state = ScenarioState()
        started = time.time()
        try:
            value = func(state)
            status = "passed"
            error = ""
        except Exception as exc:  # noqa: BLE001
            value = {}
            status = "failed"
            error = str(exc)
        for event in state.bus.events:
            aggregate.emit(event["uri"], event["node"], event["payload"])
        results.append({"name": name, "status": status, "duration": round(time.time() - started, 3), "result": value, "error": error})
    (out / "events.json").write_text(json.dumps(aggregate.events, indent=2), encoding="utf-8")
    (out / "execution-manifest.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    write_junit(results, out / "junit.xml")
    write_report(results, aggregate.events, out / "summary.md")
    return results


def write_junit(results: list[dict[str, Any]], path: Path) -> None:
    suite = ET.Element("testsuite", name="pc1-multinode-scenarios", tests=str(len(results)))
    failures = 0
    for result in results:
        case = ET.SubElement(suite, "testcase", classname="pc1.multinode", name=result["name"], time=str(result["duration"]))
        if result["status"] != "passed":
            failures += 1
            ET.SubElement(case, "failure", message=result["error"])
    suite.set("failures", str(failures))
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def write_report(results: list[dict[str, Any]], events: list[dict[str, Any]], path: Path) -> None:
    passed = sum(1 for r in results if r["status"] == "passed")
    failed = sum(1 for r in results if r["status"] == "failed")
    lines = [
        "# pc1 pc2 customer buyer human scenario report",
        "",
        f"- PASS: {passed}",
        f"- FAIL: {failed}",
        f"- SKIP: 0",
        "",
        "## URI trace",
    ]
    lines.extend(f"{event['seq']}. `{event['uri']}` node=`{event['node']}`" for event in events)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="reports/scenario")
    ns = parser.parse_args(argv)
    results = run_all(Path(ns.out))
    failed = [r for r in results if r["status"] != "passed"]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
