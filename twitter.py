# For handling twitter requests
import json
import logging
from json import JSONDecodeError

import requests
from selenium.common import NoSuchElementException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By

logger = logging.getLogger()


def twitter_post_regex():
    """
     For getting user_name and post_id from a twitter post URL
    :return: the regex to use
    """
    return r'/(\S+)/status/(\S+)'


def get_twitter_post_html(user_name: str, post_id: str):
    """
    Gets the graphical html that describes the specified post
    :param user_name: of the post
    :param post_id: of the post
    :return: the html for the post
    """
    # Get URL that provides HTML for the post. Using Twitter's oembed service, which returns
    # a json object with a html member.
    # Note: using hide_thread=false so that can also see the post being replied to, which
    # is nice for seeing context. But this takes extra vertical space so might want to set
    # this true.
    url = (f'https://publish.twitter.com/oembed?' +
           f'url=https://twitter.com/{user_name}/status/{post_id}')
    url = url + '&hide_thread=false'
    url = url + '&theme=dark'

    logger.info(f'Getting twitter html by getting url={url}')
    response = requests.get(url)
    try:
        json_result = json.loads(response.content)
        return json_result['html']
    except JSONDecodeError as e:
        logger.error(f'Could not parse twitter json. {e}')


def get_twitter_likes_str(browser: WebDriver) -> str:
    """
    Returns string indicating number of likes for a tweet. Determines the number by searching XPATH
    of html for what *appears* to be number of likes.
    :param browser: so can talk with headless browser
    :return: a string like "97 &hearts;"
    """
    logger.info(f'Getting likes string for twitter post')

    # Initialize return value
    likes_str = ''

    # Need to just look within the iframe
    iframe = browser.find_element(By.TAG_NAME, "iframe")
    browser.switch_to.frame(iframe)

    try:
        # Find the html element that contains number of likes
        xpath_str = '//article/div/a/div/span'
        likes_span_element = browser.find_element(By.XPATH, xpath_str)

        if likes_span_element:
            # Find the likes in the html <span> element
            likes_number = browser.execute_script("return arguments[0].innerText", likes_span_element)

            # Make sure the likes number wasn't actually a match to one of the other elements, one that
            # doesn't start with a number. And make sure not blank.
            if likes_number and '1' <= likes_number[0] <= '9':
                # Value number so return it as the likes string
                likes_str = f'{likes_number} &#9825;'  # &#9825; is heart outline
                logger.info(f'Found the likes string={likes_str}')
    except NoSuchElementException as e:
        logger.info(f'Could not find the twitter likes <span> element specified by XPATH={xpath_str}')

    # Switch back to the main frame so that subsequent software not confused
    browser.switch_to.default_content()

    # Done
    return likes_str


def get_twitter_post_text(browser: WebDriver) -> str:
    """
    Gets the post text for a twitter post.
    :param browser: so can talk with headless browser
    :return: post text
    """
    logger.info(f'Getting text for twitter post')

    # The return value
    post_text = ''

    # Need to just look within the iframe
    iframe = browser.find_element(By.TAG_NAME, "iframe")
    browser.switch_to.frame(iframe)

    # Find the html element that contains text of the main post
    xpath_str = '//article/div/div/span'
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


def get_twitter_rect(ratio: float, browser: WebDriver):
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
    left = iframe_rect['x'] * ratio + 2
    right = left + (iframe_rect['width'] * ratio) - 4

    browser.switch_to.frame(iframe)
    article = browser.find_element(By.TAG_NAME, 'article')
    if article:
        # Use first div in the article to get the top position
        div = article.find_element(By.TAG_NAME, 'div')
        top = (iframe_rect['y'] + div.location['y']) * ratio - 6

        # Use time element to can cut off the post there since time and remaining info not important
        time = article.find_element(By.TAG_NAME, 'time')
        if time:
            bottom = (iframe_rect['y'] + time.location['y']) * ratio - 10
        else:
            bottom = top + (article.rect['height'] * ratio) - 4
    else:
        # No <article> element so use size of iframe
        top = iframe_rect['y'] * ratio
        bottom = top + (iframe_rect['height'] * ratio)

    # Switch back to the main frame so that subsequent software not confused
    browser.switch_to.default_content()

    logger.info(f'Twitter crop rect is left={left}, top={top}, right={right}, bottom={bottom}')
    return round(left), round(top), round(right), round(bottom)
