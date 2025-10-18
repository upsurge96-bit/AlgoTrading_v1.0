# Auth Service Setup Guide

This document explains how to set up and configure the Auth Service, including database tables creation and service integration toggles.

## Using the Setup Script

The `db_setup.py` script provides multiple ways to configure the Auth Service:

### Interactive Mode

Run the script with the `-i` or `--interactive` flag to enter interactive mode:

```bash
python db_setup.py -i
```

This will display a menu where you can:
1. Toggle Kafka Integration on/off
2. Toggle Redis Integration on/off
3. Toggle Metrics Integration on/off
4. Create Database Tables
5. Exit

### Command Line Arguments

You can also use command line arguments to perform specific setup tasks:

1. Create database tables:
```bash
python db_setup.py --tables
```

2. Toggle Kafka integration:
```bash
# Turn Kafka integration on
python db_setup.py --kafka on

# Turn Kafka integration off
python db_setup.py --kafka off
```

3. Toggle Redis integration:
```bash
# Turn Redis integration on
python db_setup.py --redis on

# Turn Redis integration off
python db_setup.py --redis off
```

4. Toggle Metrics integration:
```bash
# Turn Metrics integration on
python db_setup.py --metrics on

# Turn Metrics integration off
python db_setup.py --metrics off
```

5. Combine multiple operations:
```bash
python db_setup.py --tables --kafka off --redis off --metrics off
```

## Default Behavior

If run with no arguments, the script will create database tables with the current Kafka setting unchanged.

## Quick Start Setup

For a simple deployment with minimal dependencies, run this command:

```bash
python db_setup.py --tables --kafka off --redis off --metrics off
```

This will create all necessary database tables and disable Kafka, Redis, and Metrics integrations. This is ideal for local development or simple testing environments.

## Safety Recommendations

For production environments:
- Consider disabling Kafka (`--kafka off`) if you don't need real-time messaging
- Consider disabling Redis (`--redis off`) if you don't need caching
- Consider disabling Metrics (`--metrics off`) if you don't need monitoring
- Always create tables (`--tables`) on first run or after database schema changes
- Use interactive mode (`-i`) when you're uncertain about the current configuration

## Environment Variables

The script modifies the `.env` file to set the following variables:
- `ENABLE_KAFKA`: Set to "true" or "false" to enable/disable Kafka integration
- `ENABLE_REDIS`: Set to "true" or "false" to enable/disable Redis integration
- `ENABLE_METRICS`: Set to "true" or "false" to enable/disable metrics reporting

## Notes

- Database tables will be created in the database specified by the `DATABASE_URL` in your `.env` file
- The script must be run from the project root directory to find the `.env` file
- Kafka integration requires a running Kafka broker as specified in your configuration
- Redis integration requires a running Redis server as specified in your configuration
- Metrics integration requires a running Prometheus pushgateway as specified in your configuration

## Troubleshooting

If you encounter connection errors for Redis or Metrics services, try disabling those integrations if you're not using them, or ensure that the corresponding services are running and properly configured.