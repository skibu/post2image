# Handles configuration parameters

import configparser


def init_config():
    config = configparser.ConfigParser()
    config.read('config.ini')

    http_port = config.getint('HTTP', 'http_port', fallback=9080)
    https_port = config.getint('HTTP', 'https_port', fallback=9443)

    chrome_web_browser = config.get('misc', 'chrome_web_browser', fallback=None)
    chrome_webdriver = config.get('misc', 'chrome_webdriver', fallback=None)

    # Return a dictionary with the retrieved values
    config_values = {
        'http_port': http_port,
        'https_port': https_port,
        'chrome_web_browser': chrome_web_browser,
        'chrome_webdriver': chrome_webdriver
    }

    return config_values
