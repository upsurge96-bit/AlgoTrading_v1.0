# Docker Compose Base Service for Core Module Usage
#
# This file provides a base service configuration in docker-compose.yml
# to ensure all services can properly access the core module.
#
# Usage:
#   In your docker-compose.yml file:
#
#   1. Define a base service with the common configuration:
#      
#      x-base-service: &base-service
#        build:
#          context: .
#          dockerfile: ./services/base.Dockerfile
#
#   2. Extend the base service for each service:
#      
#      auth_service:
#        <<: *base-service
#        build:
#          context: .
#          dockerfile: ./services/auth_service/Dockerfile
#        environment:
#          - SERVICE_NAME=auth_service
#

# Base service Dockerfile for common core module configuration
FROM python:3.12-slim

# Copy core module and configuration to standard locations
COPY ./core /app/core
COPY ./config /app/config
COPY ./common /app/common

# Add core and common to Python path
ENV PYTHONPATH=/app:$PYTHONPATH

# Create common directories
RUN mkdir -p /app/logs /app/data

# Pre-install commonly used packages
RUN pip install --no-cache-dir pyyaml

# Base services will extend from this
CMD ["echo", "This is a base image and should not be run directly"]