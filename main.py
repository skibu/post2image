#

import requestHandler
from config import init_config

# Read in config params from .ini file
config_values = init_config()

# Starts the webserver so can receive commands
if __name__ == '__main__':
    # Actually startup the webserver
    requestHandler.start_webserver()
