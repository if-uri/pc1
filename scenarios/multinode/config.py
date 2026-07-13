from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PcNode:
    node_id: str
    twin_user: str
    twin_role: str
    hostname: str
    vnc_port: int
    node_port: int
    profile_dir: str


def default_nodes() -> list[PcNode]:
    return [
        PcNode("pc1", "customer", "ifuri-customer", "pc1", 26080, 28765, "/profiles/pc1"),
        PcNode("pc2", "buyer", "ifuri-buyer", "pc2", 26081, 28766, "/profiles/pc2"),
    ]


def validate_nodes(nodes: list[PcNode]) -> None:
    node_ids = [n.node_id for n in nodes]
    vnc_ports = [n.vnc_port for n in nodes]
    node_ports = [n.node_port for n in nodes]
    profiles = [n.profile_dir for n in nodes]
    for label, values in {
        "node ID": node_ids,
        "VNC port": vnc_ports,
        "node port": node_ports,
        "profile dir": profiles,
    }.items():
        if len(values) != len(set(values)):
            raise ValueError(f"duplicate {label}: {values}")
    roles = {n.twin_role for n in nodes}
    required = {"ifuri-customer", "ifuri-buyer"}
    missing = required - roles
    if missing:
        raise ValueError(f"missing required role(s): {sorted(missing)}")


def compose_environment(nodes: list[PcNode] | None = None) -> dict[str, str]:
    selected = nodes or default_nodes()
    validate_nodes(selected)
    env: dict[str, str] = {}
    for node in selected:
        prefix = node.node_id.upper()
        env[f"{prefix}_NODE_ID"] = node.node_id
        env[f"{prefix}_TWIN_USER"] = node.twin_user
        env[f"{prefix}_TWIN_ROLE"] = node.twin_role
        env[f"{prefix}_HOSTNAME"] = node.hostname
        env[f"{prefix}_NOVNC_PORT"] = str(node.vnc_port)
        env[f"{prefix}_NODE_PORT"] = str(node.node_port)
        env[f"{prefix}_PROFILE_DIR"] = node.profile_dir
    return env
