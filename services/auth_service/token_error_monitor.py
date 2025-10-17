#!/usr/bin/env python3
"""
Token Error Monitor
------------------
Monitors token errors and sends alerts when thresholds are reached.
"""

import os
import sys
import time
import json
import logging
import threading
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
import requests
from collections import defaultdict, deque

# Add parent directory to path to resolve imports
parent_dir = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(parent_dir))

# Core imports
from core.utils.config_loader import ConfigLoader
from core.utils.logger import setup_logging
from core.messaging.kafka_client import KafkaConsumer
from core.messaging.web_socket import WebSocketClient

# Configure logging
setup_logging("config/logging.yaml")
logger = logging.getLogger("token_error_monitor")

# Constants
ERROR_TOPIC = "auth.token.error"
TOKEN_REFRESH_TOPIC = "auth.token.refresh"
ERROR_THRESHOLD = 3  # Number of errors before alerting
ERROR_TIME_WINDOW = 600  # 10 minutes in seconds
CONSECUTIVE_FAILURES_THRESHOLD = 2  # Number of consecutive failures before alerting
RATE_LIMIT_COOLDOWN = 1800  # 30 minutes in seconds for rate limit errors

class TokenErrorMonitor:
    """
    Monitors token errors and sends alerts.
    """
    
    def __init__(self, config_path: str = "config/monitoring.yaml"):
        """
        Initialize token error monitor.
        
        Args:
            config_path: Path to monitoring configuration file
        """
        self.config_path = config_path
        self.config = self._load_config()
        
        # Initialize Kafka consumer
        self.kafka_consumer = KafkaConsumer(ERROR_TOPIC)
        
        # Error tracking
        self.error_counts = defaultdict(int)  # broker_id -> count
        self.error_times = defaultdict(list)  # broker_id -> list of timestamps
        self.consecutive_failures = defaultdict(int)  # broker_id -> count
        self.last_alert_time = defaultdict(float)  # broker_id -> timestamp
        self.alerted_brokers = set()  # Set of broker_ids that have been alerted
        
        # Error details for tracking
        self.error_history = defaultdict(lambda: deque(maxlen=100))  # broker_id -> deque of errors
        
        # Rate limit tracking
        self.rate_limited_brokers = set()  # Set of broker_ids that are rate limited
        self.rate_limit_times = {}  # broker_id -> timestamp of rate limit start
        
        # WebSocket for live error notifications
        self.websocket = WebSocketClient(self.config.get("websocket_url", "ws://localhost:8080/ws/auth_errors"))
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load monitoring configuration.
        
        Returns:
            Monitoring configuration dictionary
        """
        try:
            config_loader = ConfigLoader()
            return config_loader.load_config(self.config_path)
        except Exception as e:
            logger.error(f"Failed to load monitoring configuration: {e}")
            # Fallback to default config
            return {
                "alert_email": "alerts@example.com",
                "smtp_server": "smtp.example.com",
                "smtp_port": 587,
                "smtp_username": "alerts@example.com",
                "smtp_password": "password",
                "webhook_url": "https://hooks.slack.com/services/xxx/yyy/zzz",
                "pagerduty_service_key": "xyz123",
                "alert_levels": {
                    "warning": {
                        "threshold": 3,
                        "time_window": 600
                    },
                    "critical": {
                        "threshold": 5,
                        "time_window": 600
                    }
                }
            }
    
    def _send_email_alert(self, broker_id: str, errors: List[Dict[str, Any]]) -> bool:
        """
        Send email alert for token errors.
        
        Args:
            broker_id: Broker identifier
            errors: List of error details
            
        Returns:
            True if email was sent successfully, False otherwise
        """
        try:
            # Get email configuration
            email_config = self.config.get("email", {})
            if not email_config:
                logger.warning("Email configuration not found, skipping email alert")
                return False
                
            smtp_server = email_config.get("smtp_server", "localhost")
            smtp_port = email_config.get("smtp_port", 25)
            smtp_username = email_config.get("username")
            smtp_password = email_config.get("password")
            from_email = email_config.get("from", "alerts@algotrading.com")
            to_email = email_config.get("to", ["admin@algotrading.com"])
            
            if isinstance(to_email, str):
                to_email = [to_email]
                
            # Create message
            msg = MIMEMultipart()
            msg["From"] = from_email
            msg["To"] = ", ".join(to_email)
            msg["Subject"] = f"ALERT: Token Errors for Broker {broker_id}"
            
            # Build message body
            body = f"Token errors detected for broker {broker_id}\n\n"
            body += f"Number of errors: {len(errors)}\n\n"
            body += "Error details:\n"
            
            for i, error in enumerate(errors[-5:], 1):  # Show the 5 most recent errors
                timestamp = error.get("timestamp", "Unknown")
                error_msg = error.get("error", "Unknown error")
                body += f"{i}. [{timestamp}] {error_msg}\n"
                
            if len(errors) > 5:
                body += f"\n... and {len(errors) - 5} more errors\n"
                
            body += "\nPlease check the auth service logs for more details."
            
            msg.attach(MIMEText(body, "plain"))
            
            # Connect to SMTP server
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                if smtp_username and smtp_password:
                    server.starttls()
                    server.login(smtp_username, smtp_password)
                    
                server.send_message(msg)
                
            logger.info(f"Email alert sent for broker {broker_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False
    
    def _send_webhook_alert(self, broker_id: str, errors: List[Dict[str, Any]]) -> bool:
        """
        Send webhook alert for token errors (e.g., Slack, Teams).
        
        Args:
            broker_id: Broker identifier
            errors: List of error details
            
        Returns:
            True if webhook alert was sent successfully, False otherwise
        """
        try:
            # Get webhook configuration
            webhook_config = self.config.get("webhook", {})
            if not webhook_config:
                logger.warning("Webhook configuration not found, skipping webhook alert")
                return False
                
            webhook_url = webhook_config.get("url")
            if not webhook_url:
                logger.warning("Webhook URL not found, skipping webhook alert")
                return False
                
            # Build payload
            severity = "critical" if len(errors) >= 5 else "warning"
            error_types = set()
            
            for error in errors:
                error_msg = error.get("error", "")
                if "rate limit" in error_msg.lower():
                    error_types.add("rate_limit")
                elif "auth" in error_msg.lower() or "unauthorized" in error_msg.lower():
                    error_types.add("authentication")
                elif "connection" in error_msg.lower() or "timeout" in error_msg.lower():
                    error_types.add("connection")
                else:
                    error_types.add("unknown")
            
            payload = {
                "text": f"*{severity.upper()} ALERT*: Token errors for broker {broker_id}",
                "attachments": [
                    {
                        "color": "danger" if severity == "critical" else "warning",
                        "fields": [
                            {
                                "title": "Broker ID",
                                "value": broker_id,
                                "short": True
                            },
                            {
                                "title": "Error Count",
                                "value": len(errors),
                                "short": True
                            },
                            {
                                "title": "Error Types",
                                "value": ", ".join(error_types),
                                "short": False
                            },
                            {
                                "title": "Latest Error",
                                "value": errors[-1].get("error", "Unknown error"),
                                "short": False
                            }
                        ],
                        "ts": int(time.time())
                    }
                ]
            }
            
            # Send webhook
            response = requests.post(webhook_url, json=payload)
            response.raise_for_status()
            
            logger.info(f"Webhook alert sent for broker {broker_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")
            return False
    
    def _send_pagerduty_alert(self, broker_id: str, errors: List[Dict[str, Any]]) -> bool:
        """
        Send PagerDuty alert for critical token errors.
        
        Args:
            broker_id: Broker identifier
            errors: List of error details
            
        Returns:
            True if PagerDuty alert was sent successfully, False otherwise
        """
        try:
            # Get PagerDuty configuration
            pagerduty_config = self.config.get("pagerduty", {})
            if not pagerduty_config:
                logger.warning("PagerDuty configuration not found, skipping PagerDuty alert")
                return False
                
            service_key = pagerduty_config.get("service_key")
            if not service_key:
                logger.warning("PagerDuty service key not found, skipping PagerDuty alert")
                return False
                
            # Only alert PagerDuty for critical errors (5 or more)
            if len(errors) < 5:
                logger.debug(f"Not enough errors for PagerDuty alert: {len(errors)}")
                return False
                
            # Build payload
            error_summary = f"Critical token errors for broker {broker_id}"
            details = {
                "broker_id": broker_id,
                "error_count": len(errors),
                "errors": [error.get("error", "Unknown error") for error in errors[-5:]]
            }
            
            payload = {
                "service_key": service_key,
                "event_type": "trigger",
                "description": error_summary,
                "incident_key": f"token_error_{broker_id}",
                "client": "TokenErrorMonitor",
                "client_url": self.config.get("dashboard_url", ""),
                "details": details
            }
            
            # Send to PagerDuty
            response = requests.post(
                "https://events.pagerduty.com/generic/2010-04-15/create_event.json",
                json=payload
            )
            response.raise_for_status()
            
            logger.info(f"PagerDuty alert sent for broker {broker_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send PagerDuty alert: {e}")
            return False
    
    def _send_websocket_notification(self, broker_id: str, error: Dict[str, Any]) -> None:
        """
        Send live notification via WebSocket.
        
        Args:
            broker_id: Broker identifier
            error: Error details
        """
        try:
            notification = {
                "type": "token_error",
                "broker_id": broker_id,
                "timestamp": datetime.utcnow().isoformat(),
                "error": error.get("error", "Unknown error"),
                "error_count": self.error_counts[broker_id]
            }
            
            self.websocket.send(json.dumps(notification))
            logger.debug(f"WebSocket notification sent for broker {broker_id}")
            
        except Exception as e:
            logger.error(f"Failed to send WebSocket notification: {e}")
    
    def _handle_rate_limit(self, broker_id: str) -> None:
        """
        Handle rate limit error for broker.
        
        Args:
            broker_id: Broker identifier
        """
        now = time.time()
        
        # If broker is not already rate limited, add to rate limited set
        if broker_id not in self.rate_limited_brokers:
            logger.info(f"Broker {broker_id} is now rate limited")
            self.rate_limited_brokers.add(broker_id)
            self.rate_limit_times[broker_id] = now
            
        # Check if rate limit cooldown has passed
        elif now - self.rate_limit_times[broker_id] > RATE_LIMIT_COOLDOWN:
            logger.info(f"Rate limit cooldown passed for broker {broker_id}")
            self.rate_limited_brokers.remove(broker_id)
            if broker_id in self.rate_limit_times:
                del self.rate_limit_times[broker_id]
    
    def _should_alert(self, broker_id: str) -> bool:
        """
        Determine if an alert should be sent.
        
        Args:
            broker_id: Broker identifier
            
        Returns:
            True if alert should be sent, False otherwise
        """
        now = time.time()
        
        # Check if broker was already alerted recently
        if broker_id in self.alerted_brokers:
            # Don't alert again within 30 minutes
            if now - self.last_alert_time[broker_id] < 1800:
                return False
        
        # Check error threshold in time window
        recent_errors = 0
        for timestamp in self.error_times[broker_id]:
            if now - timestamp < ERROR_TIME_WINDOW:
                recent_errors += 1
                
        if recent_errors >= ERROR_THRESHOLD:
            return True
            
        # Check consecutive failures
        if self.consecutive_failures[broker_id] >= CONSECUTIVE_FAILURES_THRESHOLD:
            return True
            
        return False
    
    def _process_error(self, error_event: Dict[str, Any]) -> None:
        """
        Process token error event.
        
        Args:
            error_event: Token error event from Kafka
        """
        try:
            broker_id = error_event.get("broker_id")
            if not broker_id:
                logger.warning(f"Error event missing broker_id: {error_event}")
                return
                
            # Record error
            now = time.time()
            self.error_counts[broker_id] += 1
            self.error_times[broker_id].append(now)
            self.consecutive_failures[broker_id] += 1
            
            # Add error to history
            error_with_time = error_event.copy()
            if "timestamp" not in error_with_time:
                error_with_time["timestamp"] = datetime.utcnow().isoformat()
            self.error_history[broker_id].append(error_with_time)
            
            # Check for rate limit
            error_msg = error_event.get("error", "").lower()
            if "rate limit" in error_msg or "429" in error_msg:
                self._handle_rate_limit(broker_id)
            
            # Clean up old error times
            self.error_times[broker_id] = [
                t for t in self.error_times[broker_id] 
                if now - t < ERROR_TIME_WINDOW
            ]
            
            # Send live notification
            self._send_websocket_notification(broker_id, error_event)
            
            # Check if alert should be sent
            if self._should_alert(broker_id):
                logger.warning(f"Alert threshold reached for broker {broker_id}: {self.error_counts[broker_id]} errors")
                
                # Get error history for this broker
                errors = list(self.error_history[broker_id])
                
                # Send alerts through different channels
                email_sent = self._send_email_alert(broker_id, errors)
                webhook_sent = self._send_webhook_alert(broker_id, errors)
                pagerduty_sent = self._send_pagerduty_alert(broker_id, errors)
                
                # Mark as alerted
                self.alerted_brokers.add(broker_id)
                self.last_alert_time[broker_id] = now
                
                logger.info(f"Alerts sent for broker {broker_id}: email={email_sent}, webhook={webhook_sent}, pagerduty={pagerduty_sent}")
                
        except Exception as e:
            logger.error(f"Error processing token error event: {e}")
    
    def _process_success(self, success_event: Dict[str, Any]) -> None:
        """
        Process token refresh success event.
        
        Args:
            success_event: Token refresh success event from Kafka
        """
        try:
            broker_id = success_event.get("broker_id")
            if not broker_id:
                return
                
            # Reset consecutive failures
            self.consecutive_failures[broker_id] = 0
            
            # Remove from alerted brokers if present
            if broker_id in self.alerted_brokers:
                self.alerted_brokers.remove(broker_id)
                
        except Exception as e:
            logger.error(f"Error processing token success event: {e}")
    
    def _clean_old_data(self) -> None:
        """Clean up old error data periodically."""
        now = time.time()
        
        # Clean up error times older than time window
        for broker_id in list(self.error_times.keys()):
            self.error_times[broker_id] = [
                t for t in self.error_times[broker_id] 
                if now - t < ERROR_TIME_WINDOW
            ]
            
        # Clean up rate limit times
        for broker_id in list(self.rate_limit_times.keys()):
            if now - self.rate_limit_times[broker_id] > RATE_LIMIT_COOLDOWN:
                if broker_id in self.rate_limited_brokers:
                    self.rate_limited_brokers.remove(broker_id)
                del self.rate_limit_times[broker_id]
                
        logger.debug("Cleaned up old error data")
    
    def start(self) -> None:
        """Start token error monitor."""
        logger.info("Starting token error monitor")
        
        # Start WebSocket client
        try:
            self.websocket.connect()
        except Exception as e:
            logger.warning(f"Failed to connect to WebSocket: {e}")
        
        # Start periodic cleanup
        cleanup_thread = threading.Thread(target=self._cleanup_thread, daemon=True)
        cleanup_thread.start()
        
        # Start Kafka consumers
        error_thread = threading.Thread(target=self._consume_error_events, daemon=True)
        error_thread.start()
        
        success_thread = threading.Thread(target=self._consume_success_events, daemon=True)
        success_thread.start()
        
        # Keep main thread alive
        while True:
            time.sleep(1)
    
    def _cleanup_thread(self) -> None:
        """Background thread for periodic cleanup."""
        while True:
            try:
                self._clean_old_data()
            except Exception as e:
                logger.error(f"Error in cleanup thread: {e}")
                
            # Run every minute
            time.sleep(60)
    
    def _consume_error_events(self) -> None:
        """Consume token error events from Kafka."""
        for message in self.kafka_consumer.consume():
            try:
                # Parse message
                error_event = json.loads(message.value.decode("utf-8"))
                
                # Process error event
                self._process_error(error_event)
                
            except Exception as e:
                logger.error(f"Error consuming token error event: {e}")
    
    def _consume_success_events(self) -> None:
        """Consume token refresh success events from Kafka."""
        # Create consumer for success events
        success_consumer = KafkaConsumer(TOKEN_REFRESH_TOPIC)
        
        for message in success_consumer.consume():
            try:
                # Parse message
                success_event = json.loads(message.value.decode("utf-8"))
                
                # Only process success events
                if success_event.get("success", False):
                    self._process_success(success_event)
                    
            except Exception as e:
                logger.error(f"Error consuming token success event: {e}")

def main():
    """Main entry point for token error monitor."""
    try:
        logger.info("Starting Token Error Monitor")
        
        # Initialize and start monitor
        monitor = TokenErrorMonitor()
        monitor.start()
        
    except KeyboardInterrupt:
        logger.info("Token Error Monitor stopped by user")
    except Exception as e:
        logger.critical(f"Token Error Monitor failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()