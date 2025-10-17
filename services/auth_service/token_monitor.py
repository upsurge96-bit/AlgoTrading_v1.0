#!/usr/bin/env python3
"""
Token Monitor
------------
Monitors token health and status across all brokers.
Provides API endpoints for checking token status.
"""

import os
import sys
import time
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import threading

# FastAPI imports
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

# Add parent directory to path to resolve imports
parent_dir = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(parent_dir))

# Core imports
from core.utils.config_loader import ConfigLoader
from core.utils.logger import setup_logging
from core.utils.metrics import metrics_registry
from core.db.connector import DatabaseConnector
from core.db.models import TokenRecord

# Local imports
from token_refresher_service import TokenManager

# Configure logging
setup_logging("config/logging.yaml")
logger = logging.getLogger("token_monitor")

# Create FastAPI app
app = FastAPI(
    title="Token Monitor Service",
    description="Monitors authentication token health and status",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, limit this to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Metrics
token_health_checks = metrics_registry.counter(
    "token_health_checks_total",
    "Total number of token health checks",
    ["broker", "status"]
)

@dataclass
class TokenStatus:
    """Token status information."""
    broker_id: str
    is_valid: bool
    expires_in: Optional[int] = None  # seconds until expiry, None if expired
    last_refresh: Optional[datetime] = None
    status: str = "unknown"  # "valid", "expiring", "expired", "unknown"
    error: Optional[str] = None

class TokenMonitor:
    """
    Monitors token health and status.
    """
    
    def __init__(self):
        """Initialize token monitor."""
        self.token_manager = TokenManager()
        self.db = DatabaseConnector()
        
        # Start background monitoring
        threading.Thread(target=self._background_monitor, daemon=True).start()
    
    def _background_monitor(self):
        """Background thread to monitor token health."""
        while True:
            try:
                # Check all tokens
                statuses = self.get_all_token_statuses()
                
                for status in statuses:
                    # Trigger refresh for expiring tokens
                    if status.status == "expiring" and status.expires_in and status.expires_in < 600:  # 10 minutes
                        logger.info(f"Token for broker {status.broker_id} is expiring soon, triggering refresh")
                        self.token_manager.refresh_token(status.broker_id)
            
            except Exception as e:
                logger.error(f"Error in background token monitoring: {e}")
            
            # Sleep for a while
            time.sleep(60)
    
    def get_token_status(self, broker_id: str) -> TokenStatus:
        """
        Get status of a specific token.
        
        Args:
            broker_id: Broker identifier
            
        Returns:
            Token status information
        """
        try:
            # Get token record from database
            token_record = self.db.session.query(TokenRecord).filter_by(broker_id=broker_id).first()
            
            if not token_record:
                # No token found
                return TokenStatus(
                    broker_id=broker_id,
                    is_valid=False,
                    status="unknown",
                    error="No token found"
                )
            
            # Check if token is expired
            now = datetime.utcnow()
            if token_record.expiry_time <= now:
                # Token is expired
                return TokenStatus(
                    broker_id=broker_id,
                    is_valid=False,
                    last_refresh=token_record.last_refresh,
                    status="expired",
                    error="Token expired"
                )
            
            # Calculate expiry time
            expires_in = int((token_record.expiry_time - now).total_seconds())
            
            # Determine status
            if expires_in < 300:  # 5 minutes
                status = "expiring"
            else:
                status = "valid"
                
            # Update metrics
            token_health_checks.labels(broker=broker_id, status=status).inc()
            
            return TokenStatus(
                broker_id=broker_id,
                is_valid=True,
                expires_in=expires_in,
                last_refresh=token_record.last_refresh,
                status=status
            )
            
        except Exception as e:
            logger.error(f"Error getting token status for broker {broker_id}: {e}")
            return TokenStatus(
                broker_id=broker_id,
                is_valid=False,
                status="error",
                error=str(e)
            )
    
    def get_all_token_statuses(self) -> List[TokenStatus]:
        """
        Get status of all tokens.
        
        Returns:
            List of token statuses
        """
        statuses = []
        
        # Get all brokers from config
        for broker in self.token_manager.config.get("brokers", []):
            broker_id = broker.get("id")
            if broker_id:
                status = self.get_token_status(broker_id)
                statuses.append(status)
        
        return statuses

# Create token monitor instance
token_monitor = TokenMonitor()

# API Routes

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.get("/tokens")
async def get_all_tokens():
    """Get all token statuses."""
    try:
        statuses = token_monitor.get_all_token_statuses()
        
        # Convert to dict for JSON response
        result = []
        for status in statuses:
            status_dict = {
                "broker_id": status.broker_id,
                "is_valid": status.is_valid,
                "status": status.status
            }
            
            if status.expires_in is not None:
                status_dict["expires_in"] = status.expires_in
                
            if status.last_refresh is not None:
                status_dict["last_refresh"] = status.last_refresh.isoformat()
                
            if status.error:
                status_dict["error"] = status.error
                
            result.append(status_dict)
            
        return {"tokens": result}
        
    except Exception as e:
        logger.error(f"Error retrieving token statuses: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tokens/{broker_id}")
async def get_token(broker_id: str):
    """Get token status for a specific broker."""
    try:
        status = token_monitor.get_token_status(broker_id)
        
        # Convert to dict for JSON response
        result = {
            "broker_id": status.broker_id,
            "is_valid": status.is_valid,
            "status": status.status
        }
        
        if status.expires_in is not None:
            result["expires_in"] = status.expires_in
            
        if status.last_refresh is not None:
            result["last_refresh"] = status.last_refresh.isoformat()
            
        if status.error:
            result["error"] = status.error
            
        return result
        
    except Exception as e:
        logger.error(f"Error retrieving token status for broker {broker_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tokens/{broker_id}/refresh")
async def refresh_token(broker_id: str):
    """Manually trigger token refresh for a specific broker."""
    try:
        success = token_monitor.token_manager.refresh_token(broker_id)
        
        if success:
            return {"status": "success", "message": f"Token refreshed for broker {broker_id}"}
        else:
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"status": "error", "message": f"Failed to refresh token for broker {broker_id}"}
            )
            
    except Exception as e:
        logger.error(f"Error refreshing token for broker {broker_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tokens/refresh-all")
async def refresh_all_tokens():
    """Manually trigger token refresh for all brokers."""
    try:
        results = token_monitor.token_manager.refresh_all_tokens()
        
        # Count successes and failures
        successes = sum(1 for success in results.values() if success)
        failures = len(results) - successes
        
        if failures == 0:
            return {"status": "success", "message": f"All tokens refreshed successfully ({successes} brokers)"}
        else:
            # Return partial success with details
            return JSONResponse(
                status_code=status.HTTP_207_MULTI_STATUS,
                content={
                    "status": "partial_success",
                    "message": f"{successes} token(s) refreshed successfully, {failures} failed",
                    "details": results
                }
            )
            
    except Exception as e:
        logger.error(f"Error refreshing all tokens: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def main():
    """Main entry point for token monitor service."""
    # Start FastAPI server
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()