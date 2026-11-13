# CatMapper MCP

A local Model Context Protocol (MCP) server that lets an MCP-compatible AI application use selected [CatMapper](https://catmapper.org) API operations. It communicates with the API over HTTP; it does not connect directly to the database.

## Available tools

The server supports category search, node and page inspection, dataset and metadata lookup, synchronous translation, upload status, and merge preview. Merge preview does not perform a merge. Upload status reports on an existing task; the server does not start uploads.

General editing, uploads, and merge execution are not yet exposed. Those operations need verification of their complete API-side validation and atomic-write guarantees before they can be added. This server does not expose a generic arbitrary-URL or API-call tool.

Some lookup and translation endpoints are public; authenticated endpoints use the permissions of the account associated with the supplied API key. The CatMapper API currently logs the returned rows of synchronous translations, so consider that before translating sensitive data.

## Installation

You need Python 3.10 or newer, a CatMapper API key, and an application that supports local MCP servers using `stdio`. Install from a checkout:

```sh
git clone https://github.com/ProjectCatMapper/CatMapperMCP.git
cd CatMapperMCP
python3 -m venv .venv
.venv/bin/python -m pip install .
```

On Windows, use `.venv\Scripts\python.exe` instead of `.venv/bin/python`. Configure your MCP application to run the installed `catmapper-mcp` executable with `CATMAPPER_API_KEY` in its environment. For example, the following illustrates the common `mcpServers` configuration format; consult your application's documentation for its configuration location and supported secret references:

```json
{
  "mcpServers": {
    "catmapper": {
      "command": "/absolute/path/to/CatMapperMCP/.venv/bin/catmapper-mcp",
      "env": {
        "CATMAPPER_API_KEY": "YOUR_API_KEY"
      }
    }
  }
}
```

Replace the path and configure the key using your application's secret storage or protected environment-variable facility when available. Do not paste your key into a chat, commit it to a repository, or share a configuration file containing it. On Windows, the executable is typically `.venv\Scripts\catmapper-mcp.exe`. Restart or enable the server as required by your application; it should discover the tools automatically.

`CATMAPPER_API_URL` is optional and defaults to `https://api.catmapper.org`. Use an HTTPS origin for another CatMapper deployment; plain HTTP is allowed only for localhost development. The server does not follow HTTP redirects. Generating a replacement CatMapper API key invalidates the previous key; update the MCP configuration accordingly.

## Development and tests

```sh
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m pytest -q
```

Tests use mocked or local HTTP responses and do not write to a CatMapper database. Standard output is reserved for MCP protocol communication.

## Versioning

Package versions are derived automatically from Git by `hatch-vcs` when the package is built or installed; no local Git hook or manual version-file edit is required. A release tag such as `v1.2.3` gives that release its version. Builds after a tag receive a development version containing the commit distance and Git identifier; builds with tracked uncommitted changes include a dirty marker. Untagged history also produces development versions. Create release tags deliberately when ready to release; commits and pushes do not create or publish releases automatically.

Run `.venv/bin/catmapper-mcp --version` to see the version recorded when the package was installed. Reinstall after changing commits to refresh it. Build from a Git checkout with history and tags available, or from a packaged source distribution; a GitHub-generated source archive without Git metadata is not a supported build source.

## License

[MIT](LICENSE).
