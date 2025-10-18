#!/usr/bin/env python3
"""
DB Migration Script
------------------
Creates tables for auth_service and configures service defaults.
"""

import os
import sys
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from core.db.connector import DatabaseConnector
from core.db.models import Base

def create_tables():
    """Create all tables in the database."""
    db = DatabaseConnector()
    
    # Create all tables
    try:
        Base.metadata.create_all(db.engine)
        print("✅ Successfully created all database tables")
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        sys.exit(1)
    
    # Close connection
    db.session.close()

def toggle_env_variable(variable_name, enable=True, env_file_path=".env"):
    """
    Toggle an environment variable on or off in the .env file.
    
    Args:
        variable_name: Name of the environment variable to toggle
        enable: True to set to "true", False to set to "false"
        env_file_path: Path to the .env file
        
    Returns:
        True if successful, False otherwise
    """
    env_file = Path(env_file_path)
    
    if not env_file.exists():
        print(f"⚠️ {env_file_path} file not found")
        return False
        
    # Read current .env content
    content = env_file.read_text()
    lines = content.splitlines()
    
    # Find and update the variable line
    var_found = False
    for i, line in enumerate(lines):
        if line.startswith(f"{variable_name}="):
            lines[i] = f"{variable_name}={'true' if enable else 'false'}"
            var_found = True
            break
    
    # If not found, add it
    if not var_found:
        lines.append(f"{variable_name}={'true' if enable else 'false'}")
        
    # Write updated content
    env_file.write_text("\n".join(lines))
    
    return True

def set_kafka_toggle(enable_kafka=True):
    """
    Toggle Kafka integration on or off.
    
    Args:
        enable_kafka: True to enable Kafka, False to disable
    """
    if toggle_env_variable("ENABLE_KAFKA", enable_kafka):
        status = "enabled" if enable_kafka else "disabled"
        print(f"✅ Kafka integration {status}")

def set_redis_toggle(enable_redis=True):
    """
    Toggle Redis integration on or off.
    
    Args:
        enable_redis: True to enable Redis, False to disable
    """
    if toggle_env_variable("ENABLE_REDIS", enable_redis):
        status = "enabled" if enable_redis else "disabled"
        print(f"✅ Redis integration {status}")
    
def set_metrics_toggle(enable_metrics=True):
    """
    Toggle metrics integration on or off.
    
    Args:
        enable_metrics: True to enable metrics, False to disable
    """
    if toggle_env_variable("ENABLE_METRICS", enable_metrics):
        status = "enabled" if enable_metrics else "disabled"
        print(f"✅ Metrics integration {status}")

def display_menu():
    """Display an interactive menu for setup options."""
    print("\n" + "="*50)
    print("🛠️  Auth Service Setup Menu")
    print("="*50)
    print("1. Toggle Kafka Integration (currently: {})".format(
        "ENABLED" if os.environ.get("ENABLE_KAFKA", "true").lower() in ["true", "1", "yes", "y"] else "DISABLED"
    ))
    print("2. Toggle Redis Integration (currently: {})".format(
        "ENABLED" if os.environ.get("ENABLE_REDIS", "true").lower() in ["true", "1", "yes", "y"] else "DISABLED"
    ))
    print("3. Toggle Metrics Integration (currently: {})".format(
        "ENABLED" if os.environ.get("ENABLE_METRICS", "true").lower() in ["true", "1", "yes", "y"] else "DISABLED"
    ))
    print("4. Create Database Tables")
    print("5. Exit")
    print("="*50)
    
    choice = input("Enter your choice (1-5): ")
    return choice

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Auth Service Setup Script")
    parser.add_argument("--tables", action="store_true", help="Create database tables")
    parser.add_argument("--kafka", choices=["on", "off"], help="Toggle Kafka integration on or off")
    parser.add_argument("--redis", choices=["on", "off"], help="Toggle Redis integration on or off")
    parser.add_argument("--metrics", choices=["on", "off"], help="Toggle metrics integration on or off")
    parser.add_argument("--interactive", "-i", action="store_true", help="Run in interactive mode")
    
    args = parser.parse_args()
    
    # Handle command line arguments
    if args.kafka == "on":
        set_kafka_toggle(True)
    elif args.kafka == "off":
        set_kafka_toggle(False)
        
    if args.redis == "on":
        set_redis_toggle(True)
    elif args.redis == "off":
        set_redis_toggle(False)
        
    if args.metrics == "on":
        set_metrics_toggle(True)
    elif args.metrics == "off":
        set_metrics_toggle(False)
        
    if args.tables:
        create_tables()
        
    # If no arguments or interactive mode, show menu
    if args.interactive or (not args.tables and args.kafka is None and args.redis is None and args.metrics is None):
        while True:
            choice = display_menu()
            
            if choice == "1":
                # Check current status and toggle
                current_status = os.environ.get("ENABLE_KAFKA", "true").lower() in ["true", "1", "yes", "y"]
                new_status = not current_status
                set_kafka_toggle(new_status)
                
                # Reload environment variables to reflect change immediately
                if "ENABLE_KAFKA" in os.environ:
                    os.environ["ENABLE_KAFKA"] = "true" if new_status else "false"
                    
            elif choice == "2":
                # Check current status and toggle
                current_status = os.environ.get("ENABLE_REDIS", "true").lower() in ["true", "1", "yes", "y"]
                new_status = not current_status
                set_redis_toggle(new_status)
                
                # Reload environment variables to reflect change immediately
                if "ENABLE_REDIS" in os.environ:
                    os.environ["ENABLE_REDIS"] = "true" if new_status else "false"
                    
            elif choice == "3":
                # Check current status and toggle
                current_status = os.environ.get("ENABLE_METRICS", "true").lower() in ["true", "1", "yes", "y"]
                new_status = not current_status
                set_metrics_toggle(new_status)
                
                # Reload environment variables to reflect change immediately
                if "ENABLE_METRICS" in os.environ:
                    os.environ["ENABLE_METRICS"] = "true" if new_status else "false"
                    
            elif choice == "4":
                create_tables()
                
            elif choice == "5":
                print("Exiting setup...")
                break
                
            else:
                print("Invalid choice. Please enter 1-5.")
            
            # Pause before showing menu again
            input("\nPress Enter to continue...")
    
    # If no arguments provided, default to creating tables
    if not args.interactive and not args.tables and args.kafka is None and args.redis is None and args.metrics is None:
        create_tables()