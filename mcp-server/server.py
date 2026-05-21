from mcp.server.fastmcp import FastMCP
from kubernetes import client, config

NAMESPACE = "ericsson-projects"

config.load_incluster_config()
v1 = client.CoreV1Api()

mcp = FastMCP("k8s-ericsson", host="0.0.0.0", port=8080)


@mcp.tool()
def list_pods() -> str:
    """List all pods in ericsson-projects with their status and IP."""
    pods = v1.list_namespaced_pod(NAMESPACE)
    if not pods.items:
        return "No pods found."
    rows = []
    for p in pods.items:
        cs = p.status.container_statuses or []
        ready = sum(1 for c in cs if c.ready)
        total = len(cs)
        rows.append(
            f"{p.metadata.name:<55} {p.status.phase:<12} {ready}/{total}  {p.status.pod_ip or ''}"
        )
    return "NAME" + " " * 51 + "PHASE        READY  IP\n" + "\n".join(rows)


@mcp.tool()
def get_pod_logs(pod_name: str, lines: int = 100) -> str:
    """Get the last N log lines from a pod in ericsson-projects."""
    try:
        return v1.read_namespaced_pod_log(
            name=pod_name,
            namespace=NAMESPACE,
            tail_lines=lines,
        ) or "(no output)"
    except client.exceptions.ApiException as e:
        return f"API error {e.status}: {e.reason}"


@mcp.tool()
def get_pod_events(pod_name: str) -> str:
    """Get Kubernetes events for a specific pod in ericsson-projects."""
    events = v1.list_namespaced_event(
        NAMESPACE,
        field_selector=f"involvedObject.name={pod_name}",
    )
    if not events.items:
        return f"No events for pod '{pod_name}'."
    lines = []
    for e in sorted(events.items, key=lambda x: x.last_timestamp or x.event_time or ""):
        lines.append(f"[{e.type:<7}] {e.reason:<20} {e.message}")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
