# For handling twitter requests
import json
import logging

import requests
from selenium.common import NoSuchElementException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By

logger = logging.getLogger()


def bluesky_post_regex():
    """
     For getting user_name and post_id from a bluesky post URL
    :return: the regex to use
    """
    return r'/profile/(\S+)/post/(\S+)'


def get_bluesky_post_html(user_name: str, post_id: str):
    """
    Gets the graphical html that describes the specified post
    :param user_name: of the post
    :param post_id: of the post
    :return: the html for the post
    """
    # Get URL that provides HTML for the post. Using bluesky's oembed service, which returns
    # a json object with a html member.
    url = (f'https://embed.bsky.app/oembed?' +
           f'url=https://bsky.app/profile/{user_name}/post/{post_id}&maxwidth=220')

    response = requests.get(url)
    json_result = json.loads(response.content)
    return json_result['html']


def get_bluesky_likes_str(browser: WebDriver) -> str:
    """
    Returns number of likes for a bluesky post. Determines the number by searching XPATH of html
    for what *appears* to be number of likes.
    :param browser: so can talk with headless browser
    :return: a string like "97 &hearts;"
    """
    logger.info(f'Getting likes string for bluesky post')

    # Initialize return value
    likes_str = ''

    # Need to just look within the iframe
    iframe = browser.find_element(By.TAG_NAME, "iframe")
    browser.switch_to.frame(iframe)

    # Find the html element that contains number of likes
    xpath_str = '//time/../following-sibling::div//p'
    likes_span_element = browser.find_element(By.XPATH, xpath_str)

    if likes_span_element:
        # Find the likes in the html <span> element
        try:
            likes_number = browser.execute_script("return arguments[0].innerText", likes_span_element)
            if likes_number and '1' <= likes_number[0] <= '9':
                likes_str = f'{likes_number} &#9825;'  # &#9825; is heart outline
                logger.info(f'Found the likes string={likes_str}')
        except NoSuchElementException as e:
            logger.info(f'Could not find the bluesky likes <span> element specified by XPATH={xpath_str}')

    # Switch back to the main frame so that subsequent software not confused
    browser.switch_to.default_content()

    # Done
    return likes_str


def get_bluesky_post_text(browser: WebDriver) -> str:
    """
    Gets the post text for a bluesky post.
    :param browser: so can talk with headless browser
    :return: post text
    """
    logger.info(f'Getting text for bluesky post')

    # The return value
    post_text = ''

    # Need to just look within the iframe
    iframe = browser.find_element(By.TAG_NAME, "iframe")
    browser.switch_to.frame(iframe)

    # Find the html element that contains text of the main post, which appears to be the first
    # paragraph element that is directly under a <div> instead of an <a>
    xpath_str = '//div/p'
    post_text_span_element = browser.find_element(By.XPATH, xpath_str)
    if post_text_span_element:
        # Find the text of the post in the html <span> element
        try:
            post_text = browser.execute_script("return arguments[0].innerText", post_text_span_element)
            if post_text:
                logger.info(f'Found post text={post_text}')
        except NoSuchElementException as e:
            logger.info(f'Could not find the post text <span> element specified by XPATH={xpath_str}')

    # Switch back to the main frame so that subsequent software not confused
    browser.switch_to.default_content()

    # Could not determine number of likes
    return post_text


def get_bluesky_rect(ratio: float, browser: WebDriver):
    """
    Gets the rectangle of the important part of the post. Want to use the least amount of height
    possible since BlueSky uses fixed aspect ratio for Open Graph cards and if the post is too
    tall then the image is shrunk down too much. The units are in screen pixels
    :param ratio: the peculiar pixel ratio to map from Image pixels to browser pixels
    :param browser: so can talk with headless browser
    :return:left, top, right, bottom, the coordinates of the important part of the image that should be kept
    """
    # Determine the main <article> element
    iframe = browser.find_element(By.TAG_NAME, 'iframe')

    # Determine left and right of the post. Adjusting left and right slightly to
    # not include the border, since it is visually distracting.
    iframe_rect = iframe.rect
    left = (iframe_rect['x'] + 1) * ratio
    right = left + ((iframe_rect['width'] - 2) * ratio)

    browser.switch_to.frame(iframe)

    # Determine top
    top_bar = browser.find_element(By.XPATH, '//img/../..')
    top = (iframe_rect['y'] + top_bar.rect['y'] - 2) * ratio

    # Determine bottom by using the top of the <time> element
    time = browser.find_element(By.XPATH, '//time')
    if time:
        bottom = (iframe_rect['y'] + time.rect['y'] - 7) * ratio
    else:
        # No <time> element so just use height of iframe
        bottom = top + ((iframe_rect['height'] - 5) * ratio)

    # Switch back to the main frame so that subsequent software not confused
    browser.switch_to.default_content()

    logger.info(f'Bluesky crop rect is left={left}, top={top}, right={right}, bottom={bottom}')
    return round(left), round(top), round(right), round(bottom)
