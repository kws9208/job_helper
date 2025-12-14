import logging
import sys
import os
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler


def setup_logger(logger_name, log_dir="logs", log_filename="data_collector.log"):
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger           

    formatter = logging.Formatter('[%(asctime)s] %(levelname)s | %(name)s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    log_filename = os.path.join(log_dir, log_filename)

    file_handler = TimedRotatingFileHandler(
        filename=log_filename, 
        when="midnight", 
        interval=1, 
        encoding="utf-8", 
        backupCount=30
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger