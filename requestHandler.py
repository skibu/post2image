import logging
import traceback
from http.server import BaseHTTPRequestHandler
import re

import loggingConfig
from bluesky import bluesky_post_regex, get_bluesky_post_html
from threads import threads_post_regex, get_threads_post_html
from twitter import get_twitter_post_html, twitter_post_regex

# The root logger
logger = logging.getLogger()

# Create separate logger for logging bad requests. This way they don't pollute the main log file
logger_bad_requests = loggingConfig.setup_logger("bad_requests", 'bad_requests.log')
logger_bad_requests.propagate = False


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
    def do_GET(self):
        path = self.path

        try:
            # Handle depending on which social media site the URL is for.
            # Xitter post URL is like https://x.com/becauseberkeley/status/1865482308008255873
            # Bluesky post URL is like https://bsky.app/profile/skibu.bsky.social/post/3lcmchch6js2j
            # Threads post URL is like https://www.threads.net/@lakota_man/post/DDXTHZ2Jr14
            if "/status/" in path:
                self._xitter_post(path)
            elif "/profile/" in path and "/post/" in path:
                self._bluesky_post(path)
            elif "/@" in path and "/post/" in path:
                self._threads_post(path)
            else:
                # In case unknown command specified
                msg = f'No such command {self.path}'
                logger_bad_requests.warn(f'{self.client_address[0]} : {msg}')
                return self._error_response(msg)
        except Exception as e:
            msg = 'Exception for request ' + self.path + '\n' + traceback.format_exc()
            logger.error(msg)
            return self._error_response(msg)
        finally:
            logger.debug(f'Done processing request {path}')

    def _xitter_post(self, path: str) -> None:
        """
        Handles Xitter post. The form of the URL path is
        /becauseberkeley/status/1865482308008255873
        :rtype: None
        :param path: the path of the URL that was used
        """
        print(f"Handling Xitter post: {path}")

        # Determine user_name and post_id from the path of the post
        user_name, post_id = _parse_path(path, twitter_post_regex())

        html = get_twitter_post_html(user_name, post_id)

        self._text_response(f'Xitter post: {path} for user_name={user_name} post_id={post_id} and html=\n{html}')

    def _bluesky_post(self, path: str) -> None:
        """
        Handles Bluesky post. The form of the URL path is
        /profile/gilduran.bsky.social/post/3lecu7abrlk2f
        :rtype: None
        :param path: the path of the URL that was used
        """
        print(f"Handling Bluesky post: {path}")

        # Determine user_name and post_id from the path of the post
        user_name, post_id = _parse_path(path, bluesky_post_regex())

        html = get_bluesky_post_html(user_name, post_id)

        self._text_response(f'Bluesky post: {path} for user_name={user_name} post_id={post_id} and html=\n{html}')

    def _threads_post(self, path: str) -> None:
        """
        Handles Threads post. The form of the URL path is
        /@lakota_man/post/DDXTHZ2Jr14/embed
        :rtype: None
        :param path: the path of the URL that was used
        """
        print(f"Handling Threads post: {path}")

        # Determine user_name and post_id from the path of the post
        user_name, post_id = _parse_path(path, threads_post_regex())

        html = get_threads_post_html(user_name, post_id)

        self._text_response(f'Threads post: {path} for user_name={user_name} post_id={post_id} and html=\n{html}')

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
