#!/usr/bin/env python
"""CLI management script for database operations."""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

from flask.cli import FlaskGroup
from app import create_app

cli = FlaskGroup(create_app=lambda: create_app(os.getenv("FLASK_ENV", "development")))

if __name__ == "__main__":
    cli()
