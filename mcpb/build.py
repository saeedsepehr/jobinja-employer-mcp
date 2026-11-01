"""Build jobinja-employer-mcp-<version>.mcpb (a zip) for one-click install in Claude Desktop."""
import json, zipfile
from pathlib import Path

root = Path(__file__).resolve().parent.parent
manifest = json.loads((Path(__file__).parent / "manifest.json").read_text())
out = root / "dist" / f"jobinja-employer-mcp-{manifest['version']}.mcpb"
out.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    z.write(Path(__file__).parent / "manifest.json", "manifest.json")
    for f in ("pyproject.toml", "jobinja_mcp.py", "README.md", "LICENSE"):
        z.write(root / f, f)
print(out)
