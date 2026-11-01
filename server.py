"""Compatibility entry point: `python server.py [login|http]` is the same as `jobinja-mcp`."""
import sys

import jobinja_mcp

if __name__ == "__main__":
    jobinja_mcp.main()
else:
    sys.modules[__name__] = jobinja_mcp
