# Handles configuration parameters

import configparser


def init_config():
    config = configparser.ConfigParser()
    config.read('config.ini')

    http_port = config.get('HTTP', 'http_port', fallback=9080)
    https_port = config.get('HTTP', 'https_port', fallback=9443)

    # Return a dictionary with the retrieved values
    config_values = {
        'http_port': http_port,
        'https_port': https_port
    }

    return config_values
