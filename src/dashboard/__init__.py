"""Streamlit dashboard package for legacy code modernization."""
import subprocess
import sys


def run_app():
    """CLI launcher for the dashboard."""
    subprocess.run([sys.executable, "-m", "streamlit", "run", "src/dashboard/app.py"])
