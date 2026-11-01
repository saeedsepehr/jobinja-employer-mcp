# jobinja-mcp

An unofficial [MCP](https://modelcontextprotocol.io) server for the [Jobinja](https://jobinja.ir) employer panel.
It lets an AI assistant work through your applicants the way a recruiter would: list job ads and applicants,
read profiles, team notes and resumes, star, add notes, organise resume folders and reject.

It drives the panel's own web UI with Playwright in a dedicated browser profile. It never sees or stores your
password: you sign in once by hand and the session stays in that profile on your machine.

Works on Windows, macOS and Linux, with Claude Code, Claude Desktop, OpenAI Codex CLI, ChatGPT (developer-mode
connectors) and any other MCP client.

راهنمای فارسی: [docs/README.fa.md](docs/README.fa.md)

## Tools

| Tool | What it does |
| --- | --- |
| `jobinja_status` | Is the saved session logged in, which company panel |
| `list_posts` | Job ads with per-stage applicant counts |
| `list_applicants` | Applicants of an ad; filter by status, starred, has notes; shows star, note and folder flags |
| `get_applicant` | Contact info, profile fields, Jobinja profile text, star, team notes, decision and rejection reason |
| `download_resume` / `download_resumes` | Save attached resume files (PDF) locally |
| `list_folders` / `list_folder_applicants` | Resume folders and the applicants in each |
| `create_folder` | Create a resume folder |
| `set_applicant_folders` | Add an applicant to / remove it from folders |
| `set_star` | Star / unstar an applicant |
| `add_note` / `delete_note` | Add a confidential team note / delete a mistaken one |
| `list_rejection_reasons` / `reject_applicant` | Reject with a reason (Jobinja notifies the candidate); `dry_run` fills the form without submitting |
| `restore_applicant` | Move back to "awaiting decision" |

Rejection reasons based on gender or age are intentionally not offered. Set `JOBINJA_READ_ONLY=1` to hide all
write tools. Opening an unreviewed applicant marks it as seen, exactly like opening it in the panel.

## Install

Requires Python 3.10+ and Google Chrome (or Microsoft Edge, or Playwright's bundled Chromium; see `JOBINJA_BROWSER`).

```bash
pipx install git+https://github.com/saeedsepehr/jobinja-mcp
jobinja-mcp login      # a browser window opens: sign in to the employer panel once; it closes by itself
```

(`uv tool install git+https://github.com/saeedsepehr/jobinja-mcp` works too. Without pipx/uv:
`python -m venv .venv`, then `.venv/bin/pip install .` or `.venv\Scripts\pip install .` on Windows.)

When the session expires, run `jobinja-mcp login` again. Close the MCP client first: the browser profile can only
be open in one process at a time.

## Connect a client

**Claude Code**

```bash
claude mcp add -s user jobinja -- jobinja-mcp
```

**Claude Desktop**: add to `claude_desktop_config.json` (macOS: `~/Library/Application Support/Claude/`,
Windows: `%APPDATA%\Claude\`) and restart the app:

```json
{ "mcpServers": { "jobinja": { "command": "jobinja-mcp" } } }
```

If the app cannot find the command, use its full path (`which jobinja-mcp` / `where jobinja-mcp`).

**OpenAI Codex CLI**: add to `~/.codex/config.toml`:

```toml
[mcp_servers.jobinja]
command = "jobinja-mcp"
```

**ChatGPT (developer-mode connectors)**: ChatGPT only talks to remote MCP servers over HTTPS.

```bash
jobinja-mcp http --port 8765                    # prints http://127.0.0.1:8765/<secret>/mcp
cloudflared tunnel --url http://localhost:8765  # prints a public https://….trycloudflare.com URL
```

In ChatGPT open Settings → Apps & Connectors → Advanced → enable Developer mode, then create a connector with
URL `https://….trycloudflare.com/<secret>/mcp` and no authentication. The secret path is the only protection:
anyone with the URL can use your Jobinja session, so keep it private, stop the tunnel when you are done, and
consider `JOBINJA_READ_ONLY=1` for this mode. Delete `~/.jobinja-mcp/http_token` to rotate the secret.

## Configuration

| Variable | Default |
| --- | --- |
| `JOBINJA_HOME` | `~/.jobinja-mcp` (browser profile and HTTP secret live here) |
| `JOBINJA_COMPANY` | auto-detected company slug |
| `JOBINJA_DOWNLOAD_DIR` | `~/Downloads/jobinja-resumes` |
| `JOBINJA_READ_ONLY` | unset (write tools enabled) |
| `JOBINJA_BROWSER` | `chrome`; also `msedge` or `chromium` (then run `playwright install chromium`) |
| `JOBINJA_HTTP_TOKEN` | generated on first `jobinja-mcp http` |

## Disclaimer

Not affiliated with Jobinja. The panel's markup can change and break the tools; use it within Jobinja's terms of
service and your local privacy rules, since applicant data is personal data.
