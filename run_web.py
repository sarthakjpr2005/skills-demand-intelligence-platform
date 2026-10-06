"""
Skills Demand Intelligence Platform — Web Dashboard Launcher
Run from project root:
    python run_web.py
Then open http://127.0.0.1:8000 in your browser.
"""

import sys
import uvicorn

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("  [*] SKILLS DEMAND INTELLIGENCE PLATFORM -- WEB DASHBOARD")
    print("  Starting server at: http://127.0.0.1:8000")
    print("  Press Ctrl+C to stop.")
    print("=" * 70 + "\n")
    uvicorn.run("web.app:app", host="127.0.0.1", port=8000, reload=True)

