import os
import sys
from pathlib import Path
from loguru import logger
from datetime import datetime

# Create logs directory if it doesn't exist
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Log file path with timestamp
log_file = log_dir / f"doc_flow_bot_{datetime.now().strftime('%Y%m%d')}.log"

# Remove default logger
logger.remove()

# Add console logger
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
           "<level>{level: <8}</level> | "
           "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)

# Add file logger with rotation (10 MB per file, keep 5 files)
logger.add(
    str(log_file),
    rotation="10 MB",
    retention="30 days",
    compression="zip",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    enqueue=True,  # For async support
    backtrace=True,  # Enable traceback capture
    diagnose=True,  # Enable variable values in traceback
)

def get_logger(name: str = None):
    """Get a logger with the given name.
    
    Args:
        name: Name of the logger (usually __name__)
    
    Returns:
        Configured logger instance
    """
    return logger.bind(context=name or "app")
