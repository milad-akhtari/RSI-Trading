"""Legacy Uvicorn app entry point; isolated tools import http_app instead."""
from fastapi import FastAPI
from .http_app import create_app

# Uvicorn entry point: automation.app:app
try:
    app = create_app()
except ValueError:
    app = FastAPI(title="RSI Trend Strategy Execution Gateway (unconfigured)")
