import logging
import os
import time
import traceback
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
import re

import browser
import loggingConfig
from bluesky import bluesky_post_regex, get_bluesky_post_html
from main import config_values
from threads import threads_post_regex, get_threads_post_html
from twitter import get_twitter_post_html, twitter_post_regex

# The root logger
logger = logging.getLogger()

# Create separate logger for logging bad requests. This way they don't pollute the main log file
logger_bad_requests = loggingConfig.setup_logger("bad_requests", 'bad_requests.log')
logger_bad_requests.propagate = False


def start_webserver():
    """Starts the webserver and then just waits forever"""
    server = ThreadingHTTPServer(('', config_values['http_port']), RequestHandler)

    # Respond to requests until process is killed
    server.serve_forever()


def _parse_path(path: str, regex: str) -> object:
    """
    Converts path to user_name, post_id using the specified regular expression.
    :param path:
    :param regex:
    :return: user_name, post_id
    """
    pattern = re.compile(regex)
    groups = pattern.match(path).groups()
    user_name = groups[0]
    post_id = groups[1]
    return user_name, post_id


class RequestHandler(BaseHTTPRequestHandler):
    _temp_html_file_name = 'tmp/post.html'

    def do_GET(self):
        path = self.path
        logger.info(f'Handling post at path={path}')
        print(f'Handling post at path={path}')

        try:
            html = self._get_html(path)
            logger.info(f'Got html for path={path} html=\n{html}')

            self._write_html_to_tmp_file(html)

            screenshot = browser.get_screenshot_for_html(self._temp_file_url())

            self._erase_tmp_file()

            # FIXME For now just return the html for the post
            return self._text_response(f'html=\n{html}')
        except Exception as e:
            msg = 'Exception for request ' + self.path + '\n' + traceback.format_exc()
            logger.error(msg)
            return self._error_response(msg)
        finally:
            logger.debug(f'Done processing request {path}')

    def _temp_file_url(self):
        return 'file://' + os.path.abspath(self._temp_html_file_name)

    def _write_html_to_tmp_file(self, html: str) -> None:
        """
        Open tmp file but wait till file doesn't exit. This ensures that only one thread
        can access the browser at a time
        :param html:
        """
        logger.info('Writing html to tmp file...')
        f = None
        start = time.time()
        while not f:
            try:
                f = open(self._temp_html_file_name, "x")
            except FileExistsError:
                logger.info('NOTE: temp file already exists so waiting...')
                time.sleep(0.1)
                if time.time() - start > 10.0:
                    f = open(self._temp_html_file_name, "w")

        f.write(html)
        f.close()
        logger.info("Wrote html to tmp file")

    def _erase_tmp_file(self) -> None:
        logger.info('Erasing temp file')
        os.remove(self._temp_html_file_name)

    def _get_html(self, path: str) -> str:
        """
        Gets the html that can render the specified post.
        Handle depending on which social media site the URL is for.
        Xitter post URL is like https://x.com/becauseberkeley/status/1865482308008255873
        Bluesky post URL is like https://bsky.app/profile/skibu.bsky.social/post/3lcmchch6js2j
        Threads post URL is like https://www.threads.net/@lakota_man/post/DDXTHZ2Jr14
        :param path: the path of the url used to get here
        :return: the html to render the post
        """
        if "/status/" in path:
            return self._xitter_post(path)
        elif "/profile/" in path and "/post/" in path:
            return self._bluesky_post(path)
        elif "/@" in path and "/post/" in path:
            return self._threads_post(path)
        else:
            # In case unknown command specified
            msg = f'Not a valid post "{self.path}"'
            logger_bad_requests.warn(f'{self.client_address[0]} : {msg}')
            return ''

    def _xitter_post(self, path: str) -> str:
        """
        Handles Xitter post. The form of the URL path is
        /becauseberkeley/status/1865482308008255873
        :rtype: None
        :param path: the path of the URL that was used
        """
        logger.info(f"Handling Xitter post: {path}")

        # Determine user_name and post_id from the path of the post
        user_name, post_id = _parse_path(path, twitter_post_regex())

        return get_twitter_post_html(user_name, post_id)

    def _bluesky_post(self, path: str) -> str:
        """
        Handles Bluesky post. The form of the URL path is
        /profile/gilduran.bsky.social/post/3lecu7abrlk2f
        :rtype: None
        :param path: the path of the URL that was used
        """
        logger.info(f"Handling Bluesky post: {path}")

        # Determine user_name and post_id from the path of the post
        user_name, post_id = _parse_path(path, bluesky_post_regex())

        return get_bluesky_post_html(user_name, post_id)

    def _threads_post(self, path: str) -> str:
        """
        Handles Threads post. The form of the URL path is
        /@lakota_man/post/DDXTHZ2Jr14/embed
        :rtype: None
        :param path: the path of the URL that was used
        """
        logger.info(f"Handling Threads post: {path}")

        # Determine user_name and post_id from the path of the post
        user_name, post_id = _parse_path(path, threads_post_regex())

        return get_threads_post_html(user_name, post_id)

    def _text_response(self, msg: str) -> None:
        """
        For sending back error message response
        :param msg:
        """
        response_body = bytes(msg, 'utf-8')

        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.send_header('Content-Length', str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def _error_response(self, msg: str) -> None:
        """
        For sending back error message response
        :param msg:
        """
        response_body = bytes(msg, 'utf-8')

        self.send_response(404)
        self.send_header('Content-Type', 'text/plain')
        self.send_header('Content-Length', str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)
