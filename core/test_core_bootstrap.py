# test_core_bootstrap.py
from core import get_logger, load_config

logger = get_logger("core_test")
config = load_config("/app/config/config.yaml")

logger.info(f"✅ Loaded config keys: {list(config.keys())}")
logger.info("Core system initialized successfully!")
