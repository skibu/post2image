import logging
import os

logging_dir = '/usr/local/post2image/logs/'
log_format = '%(asctime)s.%(msecs)03d - %(levelname)s : %(message)s'
date_format = '%m/%d/%y %H:%M:%S'


def setup_logger(name, log_file, level=logging.INFO):
    """To setup as many loggers as you want"""
    # Make sure directory exists
    os.makedirs(logging_dir, mode=0o777, exist_ok=True)

    # Config the handler which specifies the format of the file
    handler = logging.FileHandler(logging_dir + log_file)
    handler.setFormatter(logging.Formatter(log_format, date_format))

    # Actually create the logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)

    return logger


# Create the main logger, which is the root logger since no name is given
logger = setup_logger(None, 'imager.log', level=logging.DEBUG)
logger.info('====================== Starting post2image =============================')