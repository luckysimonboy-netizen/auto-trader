import os
import logging
from logging.handlers import RotatingFileHandler

def setup_logger(module_name: str, log_dir: str = "logs") -> logging.Logger:
    """标准化日志系统：控制台与本地文件双通道输出"""
    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger(module_name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    file_h = RotatingFileHandler(
        os.path.join(log_dir, "system.log"), maxBytes=10*1024*1024, backupCount=3, encoding="utf-8"
    )
    file_h.setFormatter(formatter)
    logger.addHandler(file_h)

    return logger
