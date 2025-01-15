# For handling threads requests
import logging

import requests
from selenium.common import NoSuchElementException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By

logger = logging.getLogger()


def threads_post_regex():
    """
     For getting user_name and post_id from a threads post URL
    :return: the regex to use
    """
    # This matches the user id by including chars until a ? or end of string is found
    return r'/(\S+)/post/([^?]+)'


def get_threads_post_html(user_name: str, post_id: str):
    """
    Gets the graphical html that describes the specified post
    :param user_name: of the post
    :param post_id: of the post
    :return: the html for the post
    """
    # Get URL that provides HTML for the post. Using threads's embed service, which returns
    # the needed html for the post.
    url = f'https://threads.net/{user_name}/post/{post_id}/embed'
    response = requests.get(url)
    return response.text


def get_threads_likes_str(browser: WebDriver) -> str:
    """
    Returns number of likes for a threads post. Determines the number by searching XPATH of html
    for what *appears* to be number of likes.
    :param browser: so can talk with headless browser
    :return: a string like "97 likes"
    """
    logger.info(f'Getting likes string for threads post')

    # Find the html element that contains number of likes
    likes_span_element = browser.find_element(By.CLASS_NAME, "MetadataContainer")

    if likes_span_element:
        # Find the likes in the html <span> element
        try:
            likes_str = browser.execute_script("return arguments[0].innerText", likes_span_element)
            logger.info(f'Found the likes string={likes_str}')
            return likes_str
        except NoSuchElementException as e:
            logger.info(f'Could not find the threads likes MetadataContainer element')

    # Could not be determined
    return ''


def get_threads_post_text(browser: WebDriver) -> str:
    """
    Gets the post text for a threads post.
    :param browser: so can talk with headless browser
    :return: post text
    """
    logger.info(f'Getting text for threads post')

    # Find the html element that contains the context
    post_text_element = browser.find_element(By.CLASS_NAME, "BodyTextContainer")

    if post_text_element:
        # Find the likes in the html <span> element
        try:
            post_text = browser.execute_script("return arguments[0].innerText", post_text_element)
            logger.info(f'Found the post text={post_text}')
            return post_text
        except NoSuchElementException as e:
            logger.info(f'Could not find the threads BodyTextContainer element')

    # Could not be determined
    return ''


def get_threads_rect(ratio: float, browser: WebDriver):
    """
    Gets the rectangle of the important part of the post. Want to use the least amount of height
    possible since BlueSky uses fixed aspect ratio for Open Graph cards and if the post is too
    tall then the image is shrunk down too much. The units are in screen pixels
    :param ratio: the peculiar pixel ratio to map from Image pixels to browser pixels
    :param browser: so can talk with headless browser
    :return:left, top, right, bottom, the coordinates of the important part of the image that should be kept
    """
    # Find the html element that contains the context
    main_container = browser.find_element(By.CLASS_NAME, 'OuterContainer')
    main_rect = main_container.rect
    left = (main_rect['x'] - 2) * ratio
    right = left + ((main_rect['width'] - 37) * ratio)

    top = (main_rect['y'] - 1) * ratio
    action_bar_container = browser.find_element(By.CLASS_NAME, "ActionBarContainer")
    if action_bar_container:
        bottom = top + (action_bar_container.location['y'] - 16) * ratio
    else:
        bottom = top + ((main_container['height'] - 16) * ratio)

    logger.info(f'Threads crop rect is left={left}, top={top}, right={right}, bottom={bottom}')
    return round(left), round(top), round(right), round(bottom)

