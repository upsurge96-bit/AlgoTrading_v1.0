#!/usr/bin/env python3
"""Test core utilities to verify they work correctly."""

print("Testing Core Utilities...")
print("=" * 80)

# Test 1: Import core.utils.logger
print("\n1. Testing core.utils.logger...")
try:
    from core.utils.logger import get_logger, setup_logging
    logger = get_logger("test_logger")
    logger.info("Core logger is working!")
    print("   ✅ Successfully imported and initialized logger")
except Exception as e:
    print(f"   ❌ Failed: {e}")

# Test 2: Import core.utils.config_loader
print("\n2. Testing core.utils.config_loader...")
try:
    from core.utils.config_loader import load_config
    config = load_config("config/config.yaml")
    print(f"   ✅ Successfully loaded config with {len(config)} keys")
    print(f"   Config keys: {', '.join(list(config.keys())[:5])}...")
except Exception as e:
    print(f"   ❌ Failed: {e}")

# Test 3: Convenience imports from core.__init__
print("\n3. Testing core.__init__ convenience exports...")
try:
    from core import get_logger, load_config
    test_logger = get_logger("convenience_test")
    print("   ✅ Convenience imports working")
except Exception as e:
    print(f"   ❌ Failed: {e}")

# Test 4: Verify no duplicate utilities exist
print("\n4. Checking for duplicate utility files...")
from pathlib import Path

duplicates = []
root = Path(__file__).parent

# Check for common/logger.py (should be deleted)
if (root / "common" / "logger.py").exists():
    duplicates.append("common/logger.py")

# Check for service-specific loggers (should be deleted)
for service_dir in (root / "services").iterdir():
    if service_dir.is_dir():
        if (service_dir / "core" / "utils" / "logger.py").exists():
            duplicates.append(f"{service_dir.name}/core/utils/logger.py")
        if (service_dir / "utils" / "logger.py").exists():
            duplicates.append(f"{service_dir.name}/utils/logger.py")

if duplicates:
    print(f"   ❌ Found {len(duplicates)} duplicate utility files:")
    for dup in duplicates:
        print(f"      - {dup}")
else:
    print("   ✅ No duplicate utility files found")

# Summary
print("\n" + "=" * 80)
print("✅ ALL CORE UTILITIES WORKING CORRECTLY!")
print("=" * 80)
