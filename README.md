"# AlgoTrading_v1.0

## Overview
AlgoTrading is a comprehensive algorithmic trading platform designed to integrate with various brokers, process market data, and execute trading strategies.

## Key Components
- **Auth Service**: Handles broker authentication and token management
- **Data Service**: Processes and stores market data
- **Strategy Service**: Implements trading strategies
- **Execution Service**: Handles order execution
- **Risk Service**: Monitors and manages trading risks
- **Monitoring Service**: Platform health monitoring

## Recent Updates
- **Time Handling Improvements**: Updated datetime handling across the platform to use timezone-aware objects
- **Token Management**: Fixed token expiry display issues in the UI
- **Enhanced Time Utilities**: Added comprehensive time utility functions in `core/utils/time_utils.py`
- **Zerodha Integration**: Improved Zerodha broker login callback and token storage

## Getting Started
1. Clone the repository
2. Configure environment variables in `config/secrets.env`
3. Run `docker-compose up` to start all services
4. Access the dashboard at http://localhost:8018

## Development
For local development:
```bash
# Build specific services
docker-compose build auth_service

# Run services
docker-compose up
```

## Time Utilities
The platform includes robust time handling utilities in `core/utils/time_utils.py`:
- `utc_now()`: Get current UTC time
- `timestamp_ms()`: Get current time as milliseconds timestamp
- `timestamp_s()`: Get current time as seconds timestamp
- `format_iso()`: Format datetime to ISO 8601
- `parse_datetime()`: Parse various datetime string formats
- `datetime_to_timestamp()`: Convert datetime to Unix timestamp
- `timestamp_to_datetime()`: Convert Unix timestamp to datetime

See [Time Handling Best Practices](docs/time_handling.md) for detailed guidance." 
