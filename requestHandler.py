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
        logger.info('==============================================')
        logger.info(f'Handling post at path={self.path}')
        print(f'Handling post at path={self.path}')

        # FIXME just for debugging
        # print(f'headers=\n{self.headers}')
        print(f'User-Agent={self.headers['User-Agent']}')
        print(f'Referer={self.headers['Referer']}')

        # If requestor is an open graph crawler then return the open graph card.
        # Otherwise return a redirect to the original post.
        if self._is_open_graph_crawler():
            self._return_open_graph_card()
        else:
            self._return_redirect_to_original_post()

    def _is_open_graph_crawler(self):
        """
        Returns true if the User-Agency header indicates that the request was for an
        Open Graph crawler (that process Oopen Graph card) instead of directly from
        a web browser.
        Bluesky crawler has used user_agent of:
          Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Bluesky Cardyb/1.1; +mailto:support@bsky.app) Chrome/W.X.Y.Z Safari/537.36
          Mozilla/5.0 (compatible; OpenGraph.io/1.1; +https://opengraph.io/;) AppleWebKit/537.36 (KHTML, like Gecko)  Chrome/51.0.2704.103 Safari/537.36
        :return: true if request was by a crawler
        """
        user_agent = self.headers['User-Agent'].lower()
        return ('OpenGraph'.lower() in user_agent or
                'Bluesky Cardyb'.lower() in user_agent)

    def _return_redirect_to_original_post(self) -> None:
        """
        Sends back redirect to the original post path but using the original domain name.
        This way the user goes to the post when they click on the link.
        """
        print("FIXME returning redirect to original post")

        new_url = f'https://x.com{self.path}'
        msg = f'Redirecting to {new_url}'

        response_body = bytes(msg, 'utf-8')
        self.send_response(302)
        self.send_header('Location', new_url)
        self.end_headers()
        self.wfile.write(response_body)

    def _return_open_graph_card(self):
        print("FIXME returning open graph card")
        path = self.path

        try:
            html = self._get_html_for_post(path)
            logger.info(f'Got html for path={path} html=\n{html}')

            self._write_html_to_tmp_file(html)
            screenshot = browser.get_screenshot_for_html(self._temp_file_url())
            self._erase_tmp_file()
            screenshot.save("tmp/cached.png")

            # Return the Open Graph card
            card_html = f"""
<html>
<head>
<meta property="og:title" content="Reposting via:" />
<meta name="twitter:title" content="Reposting via:" /> 
<meta property="og:description" content="" />

<meta property="og:type" content="article" /> <!-- probably doesn't matter -->
<meta property="og:url" content="https://www.imdb.com/title/tt0117500/" />
<meta property="og:image" content="https://m.media-amazon.com/images/M/MV5BMTc2NTQ4MjcwOV5BMl5BanBnXkFtZTgwNDUxMjE3MjI@._V1_QL75_UX642_.jpg" />
<meta property="og:image:width" content="200" />
<meta property="og:image:height" content="200" />
</head>
</html>"""
            print(f'opengraph html={card_html}')
            return self._html_response(card_html)
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

    def _get_html_for_post(self, path: str) -> str:
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

    def _html_response(self, msg: str) -> None:
        """
        For sending back html response
        :param msg:
        """
        response_body = bytes(msg, 'utf-8')

        self.send_response(200)
        self.send_header('Content-Type', 'html')
        self.send_header('Content-Length', str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def _text_response(self, msg: str) -> None:
        """
        For sending back text response
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
