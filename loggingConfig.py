import logging
import os

logging_dir = './logs/'
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
    the_logger = logging.getLogger(name)
    the_logger.setLevel(level)
    the_logger.addHandler(handler)

    return the_logger


# Create the main logger, which is the root logger since no name is given
logger = setup_logger(None, 'post2image.log', level=logging.INFO)
logger.info('====================== Starting post2image =============================')