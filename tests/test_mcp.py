"""Exercise the HTTP boundary and a real MCP stdio client without a live database."""
import asyncio
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from catmapper_mcp.api import CatMapperAPIError, CatMapperClient
from catmapper_mcp import server


def test_version_option_works_without_api_key():
    env = os.environ.copy()
    env.pop("CATMAPPER_API_KEY", None)
    result = subprocess.run([sys.executable, "-m", "catmapper_mcp.server", "--version"],
                            env=env, capture_output=True, text=True, check=True)
    assert result.stdout.startswith("server.py ")
    assert not result.stderr


def run(awaitable):
    return asyncio.run(awaitable)


def test_client_forwards_key_and_parameters_only_to_configured_api():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"results": [{"CMID": "AM1"}]})

    client = CatMapperClient("https://example.test", "test-secret", httpx.MockTransport(handler))
    result = run(client.request("GET", "/api/search", params={"term": "stone", "database": "ArchaMap"}))
    assert result == {"results": [{"CMID": "AM1"}]}
    assert str(seen[0].url) == "https://example.test/api/search?term=stone&database=ArchaMap"
    assert seen[0].headers["X-API-Key"] == "test-secret"


def test_api_error_redacts_key_and_does_not_follow_redirect():
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(302, headers={"location": "https://other.test/"}, text="secret test-secret")

    client = CatMapperClient("https://example.test", "test-secret", httpx.MockTransport(handler))
    with pytest.raises(CatMapperAPIError) as exc:
        run(client.request("GET", "/api/search"))
    assert len(requests) == 1
    assert "302" in str(exc.value)
    assert "test-secret" not in str(exc.value)
    assert "[redacted]" in str(exc.value)


def test_rejects_unsafe_config_and_paths_before_request():
    for url in ("http://example.test", "https://user:pass@example.test", "https://example.test/?key=x", "https://example.test/api"):
        with pytest.raises(ValueError):
            CatMapperClient(url, "secret")
    with pytest.raises(ValueError):
        CatMapperClient("https://example.test", " ")
    client = CatMapperClient("https://example.test", "secret")
    with pytest.raises(ValueError):
        run(client.request("GET", "//other.test/path"))


def test_invalid_path_and_search_limit_do_not_call_api(monkeypatch):
    monkeypatch.setattr(server, "_client", lambda: pytest.fail("Invalid input reached API"))
    with pytest.raises(ValueError):
        run(server.search_categories("ArchaMap", limit=0))
    # Path validation occurs when building the path. Use a client that fails if requested.
    class NoRequest:
        async def request(self, *args, **kwargs):
            pytest.fail("Invalid path reached API")
    monkeypatch.setattr(server, "_client", lambda: NoRequest())
    with pytest.raises(ValueError):
        run(server.get_node("ArchaMap", "../other"))


def test_search_and_translate_send_api_contract(monkeypatch):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"ok": True})
    client = CatMapperClient("https://example.test", "secret", httpx.MockTransport(handler))
    monkeypatch.setattr(server, "_client", lambda: client)
    run(server.search_categories("ArchaMap", term="point", contexts=["AM1", "AM2"], context_mode="any"))
    run(server.translate("ArchaMap", [{"term": "point"}], "Name", "STONE", "term", unique_rows=True))
    assert requests[0].url.path == "/api/search"
    assert requests[0].url.params.get_list("contexts") == ["AM1", "AM2"]
    assert requests[0].url.params["contextMode"] == "any"
    assert requests[1].method == "POST"
    assert requests[1].url.path == "/api/translations"
    assert json.loads(requests[1].content) == {
        "database": "ArchaMap", "table": [{"term": "point"}], "property": "Name",
        "domain": "STONE", "key": "term", "countsamename": False, "uniqueRows": True,
    }


def test_upload_status_and_merge_preview_send_api_contract(monkeypatch):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"ok": True})
    client = CatMapperClient("https://example.test", "secret", httpx.MockTransport(handler))
    monkeypatch.setattr(server, "_client", lambda: client)
    run(server.upload_status("task-123", cursor=4))
    run(server.preview_merge("ArchaMap", "AM1", "AM2"))
    assert [(request.method, request.url.path) for request in requests] == [
        ("POST", "/api/uploads/input-nodes/status"), ("POST", "/admin/merge-preview")
    ]
    assert json.loads(requests[0].content) == {"taskId": "task-123", "cursor": 4}
    assert json.loads(requests[1].content) == {"database": "ArchaMap", "keepcmid": "AM1", "deletecmid": "AM2"}
    assert all(request.headers["X-API-Key"] == "secret" for request in requests)


def test_stdio_discovery_and_tool_invocation():
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append((self.path, self.headers.get("X-API-Key")))
            body = json.dumps({"CMID": "AM123", "Name": "Test"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *args):
            pass

    http_server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=http_server.serve_forever, daemon=True)
    thread.start()
    async def exercise():
        env = dict(os.environ, CATMAPPER_API_URL=f"http://127.0.0.1:{http_server.server_port}", CATMAPPER_API_KEY="stdio-secret")
        params = StdioServerParameters(command=sys.executable, args=["-m", "catmapper_mcp.server"], env=env)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                names = {tool.name for tool in tools.tools}
                assert {"get_node", "search_categories", "translate", "preview_merge"} <= names
                assert "edit_data" not in names
                assert "queue_upload" not in names
                assert all(tool.annotations.readOnlyHint for tool in tools.tools)
                rejected = await session.call_tool("edit_data", {"database": "ArchaMap", "operation": "edit", "input": {}, "confirmed": True})
                assert rejected.isError
                result = await session.call_tool("get_node", {"database": "ArchaMap", "cmid": "AM123"})
                assert not result.isError
                assert "AM123" in str(result.content)
    try:
        run(exercise())
        assert requests == [("/api/databases/ArchaMap/nodes/AM123", "stdio-secret")]
    finally:
        http_server.shutdown()
        http_server.server_close()
        thread.join()
