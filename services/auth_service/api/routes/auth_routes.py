"""
Auth Routes
----------
Authentication related routes.
"""

from fastapi import Request, HTTPException, Depends, Security, BackgroundTasks
from fastapi.responses import RedirectResponse
from api.routes import auth_router
from core.token.manager import TokenManager
from core.token.service import TokenService

# Initialize services
token_service = TokenService()
token_manager = token_service.token_manager

@auth_router.get("/callback")
async def callback(request: Request, request_token: str = None, action: str = None, status: str = None, type: str = None):
    """
    Handle Zerodha callback after user authentication.
    
    This endpoint receives the request_token from Zerodha after successful login
    and exchanges it for an access token.
    """
    if not request_token:
        raise HTTPException(status_code=400, detail="No request token provided")
        
    if status != "success":
        raise HTTPException(status_code=400, detail=f"Authentication failed: {status}")
    
    try:
        # Use token manager to create a token using the request token
        broker_id = "zerodha"  # Default broker
        
        # Call refresh_token method with the request_token
        success = token_manager.refresh_token(broker_id, request_token)
        
        if success:
            # Redirect to home page with success message
            return RedirectResponse(url="/?status=success")
        else:
            # Redirect to home page with error message
            return RedirectResponse(url="/?status=error&message=Failed+to+exchange+token")
            
    except Exception as e:
        # Redirect to home page with error message
        error_message = str(e).replace(" ", "+")
        return RedirectResponse(url=f"/?status=error&message={error_message}")