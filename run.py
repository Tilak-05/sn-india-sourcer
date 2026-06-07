#!/usr/bin/env python3
"""
Run SN Sourcer dashboard.
Usage: python run.py
Then open: http://localhost:8000
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import uvicorn

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True, reload_dirs=["api","dashboard"])
