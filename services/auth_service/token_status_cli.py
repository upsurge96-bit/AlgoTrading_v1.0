#!/usr/bin/env python3
"""
Token Status CLI
---------------
Command-line utility for checking token status.
"""

import os
import sys
import json
import time
import argparse
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import requests
import tabulate

# Add parent directory to path to resolve imports
parent_dir = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(parent_dir))

# Core imports
from core.utils.config_loader import ConfigLoader
from core.utils.logger import setup_logging

# Configure logging
setup_logging("config/logging.yaml")
logger = logging.getLogger("token_status_cli")

# Constants
DEFAULT_API_URL = "http://localhost:8000"

def format_time_remaining(seconds: Optional[int]) -> str:
    """
    Format time remaining in human-readable format.
    
    Args:
        seconds: Seconds remaining or None
        
    Returns:
        Human-readable time string
    """
    if seconds is None:
        return "N/A"
        
    if seconds <= 0:
        return "Expired"
        
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0 or days > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or hours > 0 or days > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    
    return " ".join(parts)

def get_token_status(api_url: str, broker_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Get token status from API.
    
    Args:
        api_url: API URL
        broker_id: Optional broker ID to filter by
        
    Returns:
        Token status data
    """
    if broker_id:
        url = f"{api_url}/tokens/{broker_id}"
    else:
        url = f"{api_url}/tokens"
        
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error fetching token status: {e}")
        raise

def refresh_token(api_url: str, broker_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Refresh token via API.
    
    Args:
        api_url: API URL
        broker_id: Optional broker ID to refresh
        
    Returns:
        Refresh status data
    """
    if broker_id:
        url = f"{api_url}/tokens/{broker_id}/refresh"
    else:
        url = f"{api_url}/tokens/refresh-all"
        
    try:
        response = requests.post(url, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error refreshing token: {e}")
        raise

def print_status_table(status_data: Dict[str, Any]) -> None:
    """
    Print status data as a table.
    
    Args:
        status_data: Status data from API
    """
    if "tokens" in status_data:
        tokens = status_data["tokens"]
    else:
        tokens = [status_data]
        
    headers = ["Broker ID", "Status", "Valid", "Expires In", "Last Refresh", "Error"]
    rows = []
    
    for token in tokens:
        broker_id = token.get("broker_id", "N/A")
        status = token.get("status", "unknown")
        is_valid = "✓" if token.get("is_valid", False) else "✗"
        expires_in = format_time_remaining(token.get("expires_in"))
        last_refresh = token.get("last_refresh", "N/A")
        error = token.get("error", "")
        
        rows.append([broker_id, status, is_valid, expires_in, last_refresh, error])
    
    print(tabulate.tabulate(rows, headers=headers, tablefmt="grid"))

def handle_command(args) -> None:
    """
    Handle CLI commands.
    
    Args:
        args: Command line arguments
    """
    api_url = args.api_url or DEFAULT_API_URL
    
    try:
        if args.command == "status":
            status_data = get_token_status(api_url, args.broker_id)
            print_status_table(status_data)
            
        elif args.command == "refresh":
            print(f"Refreshing token{'s' if not args.broker_id else ''} {'for broker ' + args.broker_id if args.broker_id else ''}...")
            refresh_data = refresh_token(api_url, args.broker_id)
            print(f"Result: {refresh_data['status']}")
            if "message" in refresh_data:
                print(f"Message: {refresh_data['message']}")
                
            # Print updated status
            print("\nUpdated token status:")
            status_data = get_token_status(api_url, args.broker_id)
            print_status_table(status_data)
            
        elif args.command == "monitor":
            print(f"Monitoring token status. Press Ctrl+C to exit.")
            try:
                while True:
                    status_data = get_token_status(api_url, args.broker_id)
                    os.system('cls' if os.name == 'nt' else 'clear')
                    print(f"Token Status Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    print("=" * 80)
                    print_status_table(status_data)
                    time.sleep(args.interval)
            except KeyboardInterrupt:
                print("\nMonitoring stopped.")
                
        else:
            print(f"Unknown command: {args.command}")
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Token Status CLI")
    parser.add_argument("--api-url", help=f"Token API URL (default: {DEFAULT_API_URL})")
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    subparsers.required = True
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Check token status")
    status_parser.add_argument("--broker-id", help="Broker ID to check")
    
    # Refresh command
    refresh_parser = subparsers.add_parser("refresh", help="Refresh token")
    refresh_parser.add_argument("--broker-id", help="Broker ID to refresh")
    
    # Monitor command
    monitor_parser = subparsers.add_parser("monitor", help="Monitor token status")
    monitor_parser.add_argument("--broker-id", help="Broker ID to monitor")
    monitor_parser.add_argument("--interval", type=int, default=5, help="Refresh interval in seconds")
    
    args = parser.parse_args()
    handle_command(args)

if __name__ == "__main__":
    main()