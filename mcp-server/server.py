import os
from contextlib import asynccontextmanager

import fastmcp
import uvicorn
from fastmcp import FastMCP
from kubernetes import client, config
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

NAMESPACE = "ericsson-projects"

config.load_incluster_config()
v1 = client.CoreV1Api()

mcp = FastMCP("k8s-ericsson")


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


def run_sse_same_path() -> None:
    sse_path = os.getenv("FASTMCP_SSE_PATH", "/sse")
    message_path = sse_path

    transport = SseServerTransport(message_path)

    class SseSamePathEndpoint:
        def __init__(self, server: FastMCP):
            self._server = server

        async def __call__(self, scope, receive, send):
            if scope.get("type") != "http":
                await PlainTextResponse("Unsupported", status_code=400)(scope, receive, send)
                return

            method = scope.get("method", "").upper()
            if method == "GET":
                async with transport.connect_sse(scope, receive, send) as streams:
                    await self._server._mcp_server.run(
                        streams[0],
                        streams[1],
                        self._server._mcp_server.create_initialization_options(),
                    )
                return

            if method == "POST":
                await transport.handle_post_message(scope, receive, send)
                return

            await PlainTextResponse("Method Not Allowed", status_code=405)(scope, receive, send)

    @asynccontextmanager
    async def lifespan(_app: Starlette):
        async with mcp._lifespan_manager():
            yield

    app = Starlette(
        debug=fastmcp.settings.debug,
        routes=[
            Route(
                sse_path,
                endpoint=SseSamePathEndpoint(mcp),
                methods=["GET", "POST"],
            )
        ],
        lifespan=lifespan,
    )

    host = os.getenv("FASTMCP_HOST", os.getenv("HOST", fastmcp.settings.host))
    port = int(os.getenv("FASTMCP_PORT", os.getenv("PORT", str(fastmcp.settings.port))))
    log_level = (os.getenv("FASTMCP_LOG_LEVEL") or fastmcp.settings.log_level).lower()

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=log_level,
        lifespan="on",
        timeout_graceful_shutdown=2,
        ws="websockets-sansio",
    )


if __name__ == "__main__":
    run_sse_same_path()
