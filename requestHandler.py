import logging
import os
from typing import Optional
import time
import traceback
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
import re
from io import BytesIO
from urllib.parse import urlparse

from PIL import Image

import browser
import loggingConfig
from bluesky import bluesky_post_regex, get_bluesky_post_html
from main import config_values
from threads import threads_post_regex, get_threads_post_html
from twitter import get_twitter_post_html, twitter_post_regex
from stable_hash import stable_hash_str

# The root logger
logger = logging.getLogger()

# Create separate logger for logging bad requests. This way they don't pollute the main log file
logger_bad_requests = loggingConfig.setup_logger("bad_requests", 'bad_requests.log')
logger_bad_requests.propagate = False

# So can erase tmp file at startup
_first_time = True


def start_webserver():
    """Starts the webserver and then just waits forever"""
    server = ThreadingHTTPServer(('', config_values['http_port']), RequestHandler)

    # Respond to requests until process is killed
    server.serve_forever()


# noinspection PyMethodMayBeStatic
class RequestHandler(BaseHTTPRequestHandler):
    _temp_html_file_name = 'tmp/post.html'
    _images_directory = 'images'
    _cache_directory = 'cache'

    def do_GET(self):
        # If first time run then make sure there is no tmp file lying around from before.
        # Wanted to put this into __init__ but then it was called for every request
        global _first_time
        if _first_time:
            logger.info(f'First web request to process so initialing web server...')
            self._erase_tmp_file()
            _first_time = False

        logger.info(f'============== Handling request for path={self.path} ==============')

        # If getting image from cache, do so...
        if self.path.startswith('/' + self._images_directory):
            image_local_file_name = self.path[1:]  # remove the first slash
            self._return_image(image_local_file_name)
            return

        # If requestor is an open graph crawler then return the open graph card.
        # Otherwise return a redirect to the original post.
        if self._is_open_graph_crawler():
            self._return_open_graph_card()
        else:
            self._return_redirect_to_original_post()

    def _return_image(self, local_file_name: str) -> None:
        """
        Returns image at local_file_name as an http response
        :param local_file_name:
        """
        # Read in image from file
        image = Image.open(local_file_name)

        # Create the image response
        self.send_response(200)
        self.send_header('Content-Type', 'image/png')

        # Return object as a PNG (though should already be a PNG)
        img_bytes_io = BytesIO()
        image.save(img_bytes_io, 'PNG')
        img_bytes_io.seek(0)
        img_bytes = img_bytes_io.read()

        # Finish up the response headers
        content_length = len(img_bytes)
        self.send_header('Content-Length', str(content_length))
        self.end_headers()

        # Write out the body
        self.wfile.write(img_bytes)

        logger.info(f'Returned requested image {local_file_name}')

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
        user_agent = self.headers['User-Agent']
        if user_agent:
            user_agent = user_agent.lower()
        return ('OpenGraph'.lower() in user_agent or
                'Bluesky Cardyb'.lower() in user_agent)

    def _return_redirect_to_original_post(self) -> None:
        """
        Sends back redirect to the original post path but using the original domain name.
        This way the user goes to the post when they click on the link.
        """
        logger.info("Returning redirect to original post")

        new_url = f'https://x.com{self.path}'
        msg = f'Redirecting to {new_url}'

        response_body = bytes(msg, 'utf-8')
        self.send_response(302)
        self.send_header('Location', new_url)
        self.end_headers()
        self.wfile.write(response_body)

    def _image_file_name(self, path: str) -> str:
        """
        Converts the path into a hash that can be used as a filename.
        :param path: source of hash
        :return: file name of image associated with path
        """
        # Make sure the directory has been created
        os.makedirs(self._images_directory, exist_ok=True)

        return self._images_directory + '/' + stable_hash_str(path) + '.png'

    def _get_cache_filename(self, path: str) -> str:
        return self._cache_directory + '/' + stable_hash_str(path) + '_card.html'

    def _get_card_from_cache(self, path: str) -> Optional[str]:
        filename = self._get_cache_filename(path)

        logger.info(f'Seeing if request path={path} is stored as cache file={filename}')
        try:
            f = open(filename, "r")
            html = f.read()
            f.close()
            logger.info(f'For path={path} using cache file={filename} html=\n{html}')
            return html
        except FileNotFoundError as e:
            # No cache file that could be opened
            return None

    def _put_card_into_cache(self, path: str, html: str) -> None:
        # Make sure cache directory exists
        os.makedirs(self._cache_directory, exist_ok=True)

        # Store html into the file
        filename = self._get_cache_filename(path)
        try:
            f = open(filename, "w")
            f.write(html)
            f.close()
            logger.info(f'For path={path} cached into file={filename} html=\n{html}')
        except FileNotFoundError as e:
            logger.error(f'Could not write cache file {filename} {str(e)}')

    def _return_open_graph_card(self) -> None:
        # Determine the path. If there is a query string represented by a '?' then trim it off
        # so that it doesn't complicate things. This is important because sometimes post URLs
        # will include a query string with superfluous info.
        path = urlparse(self.path).path
        logger.info(f'Will be returning Open Graph card for path={path}')

        try:
            # If cached card exists then return it
            cached_card_html = self._get_card_from_cache(path)
            if cached_card_html:
                logger.info(f'returning cached opengraph card html=\n{cached_card_html}')
                return self._html_response(cached_card_html)

            # Cached card doesn't exist so create it
            # Get the html for rendering the post
            html = self._get_html_for_post(path)
            if not html:
                # This can happen when Twitter tries to get card before the url is correct.
                # So it isn't truly an error to log.
                logger.info(f'Could not get html for path={path} so returning error http response')
                return self._error_response(f'Could not get html for path={path}')
            logger.info(f'Obtained html for path={path} html=\n{html}')

            self._write_html_to_tmp_file(html)
            screenshot_image, num_likes = browser.get_screenshot_for_html(self._temp_file_url())
            self._erase_tmp_file()

            # Save the image into the cache
            image_local_file_name = self._image_file_name(path)
            image_url = 'http://' + config_values['domain'] + '/' + image_local_file_name
            screenshot_image.save(image_local_file_name)
            logger.info(f'Stored image in cache as file {image_local_file_name}')

            # Generate the title to display. Currently Bluesky will output a title no matter what, so might
            # as well make it useful. Bluesky also displays the domain name underneath. Therefore using
            # 'Reposted via' as the title. And adding the number of likes if it is available. This is especially
            # nice since trying to trim number of likes from the image of the post so that the image is not
            # to tall.
            title = 'Reposted via'
            if num_likes:
                title = f'&hearts; {num_likes} - ' + title

            # Determine the image size so that it can be returned in the link card (even though Bluesky
            # currently doesn't use that info
            width, height = screenshot_image.size

            # Return the Open Graph card
            card_html = f"""
<html>
<head>
<!-- OpenGraph card for post {path} -->
<meta property="og:title" content="{title}" />
<meta name="twitter:title" content="{title}" /> 
<meta property="og:description" content="" />
<meta property="og:type" content="image" /> <!-- probably doesn't matter -->
<meta property="og:image" content="{image_url}" />
<meta property="og:image:width" content="{width}" /> <!-- doesn't work on Bluesky et al -->
<meta property="og:image:height" content="{height}" />  <!-- doesn't work on Bluesky et al -->
</head>
</html>"""

            # Cache the card html in case accessed again
            self._put_card_into_cache(path, card_html)

            logger.info(f'returning opengraph card html={card_html}')
            return self._html_response(card_html)
        except:
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
        logger.info(f'Writing html to tmp file {self._temp_html_file_name} ...')
        f = None
        start = time.time()
        while not f:
            try:
                f = open(self._temp_html_file_name, "x")
            except FileExistsError:
                logger.info(f'NOTE: temp file {self._temp_html_file_name} already exists so waiting for '
                            f'it to disappear, or for 10 secs...')
                time.sleep(2.0)  # FIXME time.sleep(0.1)
                if time.time() - start > 10.0:
                    f = open(self._temp_html_file_name, "w")

        f.write(html)
        f.close()
        logger.info(f'Wrote html to tmp file {self._temp_html_file_name}')

    def _erase_tmp_file(self) -> None:
        """
        Erases the tmp file used to both store the html and to make sure that only single request
        accesses the browser at a time. This should also be done at startup in case this program
        terminated without cleaning up that file by erasing it.
        :return:
        """
        logger.info(f'Erasing temp file {self._temp_html_file_name}')
        try:
            os.remove(self._temp_html_file_name)
        except FileNotFoundError:
            logger.info(f'There was no tmp file {self._temp_html_file_name} to erase')

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

    def _parse_path(self, path: str, regex: str) -> tuple[str, str]:
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

    def _xitter_post(self, path: str) -> str:
        """
        Handles Xitter post. The form of the URL path is
        /becauseberkeley/status/1865482308008255873
        :rtype: None
        :param path: the path of the URL that was used
        """
        logger.info(f"Handling Xitter post: {path}")

        # Determine user_name and post_id from the path of the post
        user_name, post_id = self._parse_path(path, twitter_post_regex())

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
        user_name, post_id = self._parse_path(path, bluesky_post_regex())

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
        user_name, post_id = self._parse_path(path, threads_post_regex())

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
