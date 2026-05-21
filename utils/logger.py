import logging
import os

def setup_logger(name="AJIOMonitor"):
    """
    Sets up a modular, nicely formatted console logger.
    If the environment variable DEBUG=true is set, it enables logging.DEBUG level.
    """
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers if setup is called multiple times
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        # Check environment variable for Debug Mode
        debug_env = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
        if debug_env:
            logger.setLevel(logging.DEBUG)
            logger.debug("Logger configured in DEBUG mode. Extra diagnostics will be logged.")
        else:
            logger.setLevel(logging.INFO)
            
    return logger
