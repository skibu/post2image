# Handles configuration parameters

import configparser


def init_config():
    config = configparser.ConfigParser()
    config.read('config.ini')

    http_port = config.getint('HTTP', 'http_port', fallback=9080)
    https_port = config.getint('HTTP', 'https_port', fallback=9443)
    certfile = config.get('HTTP', 'certfile', fallback='certfile.pem')
    keyfile = config.get('HTTP', 'keyfile', fallback='keyfile.pem')
    domain = config.get('HTTP', 'domain', fallback='xrosspost.com')

    chrome_web_browser = config.get('misc', 'chrome_web_browser', fallback=None)
    chrome_webdriver = config.get('misc', 'chrome_webdriver', fallback=None)

    readme_url = config.get('misc', 'readme_url')

    allowable_cache_file_age_hours = config.get('misc', 'allowable_cache_file_age_hours', fallback=24)

    # Return a dictionary with the retrieved values
    config_values = {
        'http_port': http_port,
        'https_port': https_port,
        'certfile': certfile,
        'keyfile': keyfile,
        'domain': domain,
        'chrome_web_browser': chrome_web_browser,
        'chrome_webdriver': chrome_webdriver,
        'allowable_cache_file_age_hours': allowable_cache_file_age_hours,
        'readme_url': readme_url
    }

    return config_values
