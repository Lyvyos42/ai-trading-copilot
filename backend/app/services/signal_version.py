"""
The version stamped on every Copilot signal: which build of the signal logic produced it.

On Render, RENDER_GIT_COMMIT names the deployed commit; locally there is no such variable and the
signal says "copilot-local". A signal keeps the version it was created with, so the calibration can
separate signals from different versions of the logic instead of mixing them.
"""
import os

SIGNAL_VERSION = "copilot-" + ((os.environ.get("RENDER_GIT_COMMIT") or "")[:7] or "local")
