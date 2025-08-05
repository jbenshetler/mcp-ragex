#!/usr/bin/env python3
"""Test file for enhanced symbol extraction"""

import os
import sys
from pathlib import Path
from typing import List, Dict
import requests
from dataclasses import dataclass

# Module-level constants
API_KEY = os.environ.get("API_KEY", "default_key")
BASE_URL = "https://api.example.com"
MAX_RETRIES = 3
CONFIG_PATH = os.getenv("CONFIG_PATH", "/etc/config")
DATABASE_URL = os.environ["DATABASE_URL"]

# Configuration dictionary
settings = {
    "debug": True,
    "timeout": 30
}

class APIClient:
    """Client for interacting with the API"""
    
    def __init__(self):
        self.api_key = API_KEY
        self.base_url = BASE_URL
    
    def get_data(self) -> Dict:
        """Fetch data from the API"""
        return requests.get(f"{self.base_url}/data")

def process_config():
    """Process configuration from environment"""
    db_host = os.environ.get("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    return {
        "host": db_host,
        "port": db_port
    }

async def main():
    """Main entry point"""
    client = APIClient()
    data = client.get_data()
    config = process_config()
    print(f"Connected to {config['host']}:{config['port']}")