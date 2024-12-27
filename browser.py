# For using Chrome browser to convert complicated html to an image
import logging
from io import BytesIO
from typing import Optional

from PIL import Image
from selenium import webdriver
from selenium.common import NoSuchElementException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from main import config_values

logger = logging.getLogger()

_browser: Optional[WebDriver] = None


def browser_init() -> None:
    """
    Initializes browser if haven't done so yet
    """
    global _browser
    if _browser is not None:
        return

    # Options listed at https://www.selenium.dev/documentation/webdriver/drivers/options/
    options = webdriver.ChromeOptions()
    # to get rid of warning message at top of page
    options.add_experimental_option("excludeSwitches", ['enable-automation']);
    # To run without actual displaying browser window
    options.add_argument('--headless=new')

    # If chrome_web_browser specified then use it. Otherwise uses selenium default value
    if config_values['chrome_web_browser']:
        options.binary_location = config_values['chrome_web_browser']

    # If chrome_webdriver specified then use it. Otherwise uses selenium default value
    if config_values['chrome_webdriver']:
        service = webdriver.ChromeService(executable_path=config_values['chrome_webdriver'])
    else:
        service = None

    _browser = webdriver.Chrome(options=options, service=service)

    # Note: Chrome only goes down to 400px or 500px width. To get skinnier post need to put the
    # post html within a <div style="max-width: 399px"> </div> block.
    _browser.set_window_size(400, 1000)


def browser_get(url) -> None:
    """
    Gets the URL using the browser and waits till the post is fully loaded
    :param url:
    :return:
    """
    browser_init()
    _browser.get(url)


def get_screenshot() -> Image:
    """
    Takes screenshot of visible part of the browser window and returns it as a Pillow Image
    :return:
    """
    png = _browser.get_screenshot_as_png()
    return Image.open(BytesIO(png))


def get_image_pixels_per_browser_pixel(image: Image):
    """
    Pixels in browser are not the same as pixels for the screen or for a
    screenshot. Depends on display resolution. To determine the ratio
    need to compare width of image to current width of browser window.
    Need to look at width since can get width of content using
    get_window_size(), whereas that function includes browser toolbar
    when looking at height. Also, need to use get_window_size() to get
    the width since it might be different than the requested width
    since the browser likely has a minimum width (e.g. 500px for Chrome,
    usually)
    :param image: Image
    """
    window_size = _browser.get_window_size()
    return image.size[0] / window_size['width']


def get_post_element():
    """
    Returns the html element, like a div or iframe, that defines the rectangle that the post is displayed within
    :return: the html element
    """
    # Want find_element() to return immediately if the element can't be found. This way
    # can handle posts from different social media systems
    _browser.implicitly_wait(0)

    # If threads then want the div with class "OuterContainer"
    try:
        return _browser.find_element(By.CLASS_NAME, "OuterContainer")
    except NoSuchElementException as e:
        try:
            # If twitter or bluesky post then want the iframe
            print("There was no threads OuterContainer so returning iframe")
            return _browser.find_element(By.TAG_NAME, "iframe")
        except NoSuchElementException as e:
            print(f"Could not find the html element for the post. {e.msg}")
            return None


def wait_till_loaded():
    """
    Waits till the post html has been fully loaded.
    :return:
    """
    # First need to determine if the post uses an iframe. If it doesn't then the get()
    # will have made sure that the post is fully loaded, so all done. But if an iframe
    # exists then need to make sure that it has been loaded.
    try:
        # Have find_element() return immediately
        _browser.implicitly_wait(0)

        # See if iframe is being used. If not then NoSuchElementException will occur
        iframe = _browser.find_element(By.TAG_NAME, "iframe")
        print(f'iframe dom id = {iframe.get_dom_attribute("id")}')

        # switch to selected iframe document so can see if its sub-elements are ready
        _browser.switch_to.frame(iframe)

        # Find an element in  the iframe that will be displayed once iframe fully loaded.
        # Since the elements in the frame might not have been loaded yet need to
        # give it a few seconds.
        _browser.implicitly_wait(5)
        element = _browser.find_element(By.TAG_NAME, 'div')

        # Wait until the element has actually been displayed
        wait = WebDriverWait(_browser, timeout=5)
        wait.until(lambda d: element.is_displayed())

        # Switch back to the main frame so that subsequent software not confused
        _browser.switch_to.default_content()

        print('The post is now fully loaded')
    except NoSuchElementException as e:
        # There was no iframe so done since the get() would have waited till page loaded
        print("No iframe used so page must already be fully loaded")
        return


def get_rect(screenshot) -> object:
    """
    Gets the rectangle of the iframe, including 1 px margin around it. The units are
    in screen pixels and can be used to crop screenshot image to just the iframe with
    small border.
    :param screenshot:
    :return:
    """
    # Make sure that post is first fully loaded
    wait_till_loaded()

    post_element = get_post_element()
    print(f'post_element dom id = {post_element.get_dom_attribute("id")}')

    # Determine dimensions of the element
    ratio = get_image_pixels_per_browser_pixel(screenshot)
    rect = post_element.rect
    left = rect['x'] * ratio - 1
    right = left + (rect['width'] * ratio) + 2
    top = rect['y'] * ratio - 1
    bottom = top + (rect['height'] * ratio) + 2

    return left, top, right, bottom
