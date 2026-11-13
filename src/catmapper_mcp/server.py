"""Local stdio MCP adapter to the CatMapper HTTP API."""
from __future__ import annotations

import argparse
from importlib.metadata import version
from typing import Any, Literal
from urllib.parse import quote

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .api import CatMapperClient

mcp = FastMCP("CatMapper")
READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True)


def _client():
    return CatMapperClient.from_env()


def _segment(value: str) -> str:
    if not value or value in (".", "..") or "/" in value or "\\" in value:
        raise ValueError("Invalid path component")
    return quote(value, safe="")


def _params(**values):
    return {k: v for k, v in values.items() if v is not None}


@mcp.tool(annotations=READ)
async def search_categories(database: str, term: str = "", property: Literal["Name", "CMID", "Key"] = "Name", domain: str = "CATEGORY", dataset: str | None = None, year_start: int | None = None, year_end: int | None = None, country: str | None = None, contexts: list[str] | None = None, context_mode: Literal["all", "any"] = "all", limit: int = 100) -> Any:
    """Search categories and entities. Database is ArchaMap or SocioMap; contexts and dataset are CMIDs."""
    if not 1 <= limit <= 10000:
        raise ValueError("limit must be between 1 and 10000")
    return await _client().request("GET", "/api/search", params=_params(database=database, term=term, property=property, domain=domain, dataset=dataset, yearStart=year_start, yearEnd=year_end, country=country, contexts=contexts, contextMode=context_mode, limit=limit))


@mcp.tool(annotations=READ)
async def get_node(database: str, cmid: str) -> Any:
    """Get a node's properties and USES relationships by CMID."""
    return await _client().request("GET", f"/api/databases/{_segment(database)}/nodes/{_segment(cmid)}")


@mcp.tool(annotations=READ)
async def get_node_page(database: str, cmid: str) -> Any:
    """Get the explore-page representation of a CatMapper node."""
    return await _client().request("GET", f"/api/databases/{_segment(database)}/nodes/{_segment(cmid)}/page.json")


@mcp.tool(annotations=READ)
async def get_dataset(database: str, cmid: str, domain: str | None = None, children: bool = False) -> Any:
    """Get a dataset's details and category data; optionally filter by domain."""
    return await _client().request("GET", "/api/dataset", params=_params(database=database, cmid=cmid, domain=domain, children=str(children).lower()))


@mcp.tool(annotations=READ)
async def list_datasets(database: str) -> Any:
    """List datasets in a CatMapper database."""
    return await _client().request("GET", "/api/datasets", params={"database": database})


@mcp.tool(annotations=READ)
async def list_domains(database: str) -> Any:
    """List public domains in a CatMapper database."""
    return await _client().request("GET", f"/api/databases/{_segment(database)}/metadata/domains")


@mcp.tool(annotations=READ)
async def list_subdomains(database: str) -> Any:
    """List public subdomains in a CatMapper database."""
    return await _client().request("GET", f"/api/databases/{_segment(database)}/metadata/subdomains")


@mcp.tool(annotations=READ)
async def list_properties(database: str) -> Any:
    """List metadata properties in a CatMapper database."""
    return await _client().request("GET", f"/api/databases/{_segment(database)}/metadata/properties")


@mcp.tool(annotations=READ)
async def translate(database: str, table: list[dict[str, Any]], property: str, domain: str, key: str, term: str | None = None, dataset: str | None = None, country: str | None = None, context: str | None = None, year_start: int | None = None, year_end: int | None = None, countsamename: bool = False, unique_rows: bool = False) -> Any:
    """Translate tabular category data synchronously. The CatMapper API may log returned rows."""
    return await _client().request("POST", "/api/translations", json=_params(database=database, table=table, property=property, domain=domain, key=key, term=term, dataset=dataset, country=country, context=context, yearStart=year_start, yearEnd=year_end, countsamename=countsamename, uniqueRows=unique_rows))


@mcp.tool(annotations=READ)
async def upload_status(task_id: str, cursor: int = 0) -> Any:
    """Check a queued upload's status and progress using its task ID."""
    return await _client().request("POST", "/api/uploads/input-nodes/status", json={"taskId": task_id, "cursor": cursor})


@mcp.tool(annotations=READ)
async def preview_merge(database: str, keep_cmid: str, delete_cmid: str) -> Any:
    """Preview a category merge and identify cyclic parent references. Does not apply the merge."""
    return await _client().request("POST", "/admin/merge-preview", json={"database": database, "keepcmid": keep_cmid, "deletecmid": delete_cmid})


def main():
    parser = argparse.ArgumentParser(description="CatMapper local MCP server")
    parser.add_argument("--version", action="version", version=f"%(prog)s {version('catmapper-mcp')}")
    parser.parse_args()
    # Fail early without writing to stdout, which is reserved for MCP protocol messages.
    CatMapperClient.from_env()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
