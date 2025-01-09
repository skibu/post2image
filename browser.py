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
    # FIXME options.add_argument('--headless=new')

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
    _browser.set_window_size(600, 1000)


def get_screenshot_for_html(url: str) -> Image:
    """
    Loads specified URL into the browser, takes a screenshot of it as a PNG,
    and then returns a cropped version of the screenshot.
    :param url: url of the file containing the html that describes the post. Can be on localhost.
    :return: resulting image
    """
    logger.info(f'Loading headless browser using html in url={url}')

    # Load specified URL into the browser
    load_url(url)

    # Wait till html fully loaded, include javascript and iframes
    logger.info(f'Waiting till html loaded...')
    wait_till_loaded()
    logger.info(f'html loaded so can now get screenshot of post')
    # Take a screenshot of the url content
    screenshot = get_screenshot()
    logger.info(f'Got screenshot {screenshot}')

    # Crop it to remove surrounding white space
    rect = get_rect(screenshot)
    cropped_screenshot = screenshot.crop(rect)

    # FIXME For debugging save the images
    screenshot.save('tmp/image.png')
    cropped_screenshot.save('tmp/cropped.png')

    properly_sized_image = get_properly_sized_image(cropped_screenshot)
    return properly_sized_image


def get_properly_sized_image(img: Image) -> Image:
    desired_w = 1200
    desired_h = 630
    img_w, img_h = img.size
    if img_h <= desired_h:
        return img
    else:
        # Shrink the image so that height is at limit of desired_h
        shrunken_size = round(img_w * (desired_h / img_h)), desired_h
        img.thumbnail(shrunken_size, Image.Resampling.LANCZOS)

        # Create background transparent image that is desired size
        proper_img = Image.new(mode="RGBA",
                               size=(desired_w, desired_h),
                               color=(0, 0, 0, 0))

        # Write the shrunken image onto the transparent background
        img_w = img.width
        offset = ((desired_w - img_w) // 2, 0)
        proper_img.paste(img, offset)

        # Return the shrunken image with transparent sides
        return proper_img


def load_url(url) -> None:
    """
    Fetches the URL using the browser and waits till the post
    (but not any iframe) is fully loaded
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
            logger.info("There was no Threads OuterContainer so returning iframe")
            return _browser.find_element(By.TAG_NAME, "iframe")
        except NoSuchElementException as e:
            logger.error(f"Could not find the html element for the post. {e.msg}")
            return None


def wait_till_loaded():
    """
    Waits till the post html has been fully loaded.
    First need to determine if the post uses an iframe. If it doesn't then the get()
    will have made sure that the post is fully loaded, so all done. But if an iframe
    exists then need to make sure that it has been loaded.
    :return:
    """
    logger.info(f'Waiting till html fully loaded and rendered...')

    try:
        # Have find_element() return immediately
        _browser.implicitly_wait(0)

        # See if iframe is being used. If not then NoSuchElementException will occur
        iframe = _browser.find_element(By.TAG_NAME, "iframe")
        logger.info(f'iframe found. DOM id = {iframe.get_dom_attribute("id")}')

        # switch to selected iframe document so can see if its sub-elements are ready
        _browser.switch_to.frame(iframe)

        # Find an element in the iframe that will be displayed once iframe fully loaded.
        # Since the elements in the frame might not have been loaded yet need to
        # give it a few seconds.
        _browser.implicitly_wait(5)
        element = _browser.find_element(By.TAG_NAME, 'div')
        logger.info(f'Found div html element within the iframe. DOM id= {element.get_dom_attribute("id")}')

        # Wait until the element has actually been displayed
        logger.info(f'Waiting for div element to be displayed...')
        wait = WebDriverWait(_browser, timeout=5)
        wait.until(lambda d: element.is_displayed())
        logger.info(f'div element is now displayed...')

        # Switch back to the main frame so that subsequent software not confused
        _browser.switch_to.default_content()

        logger.info('The post is now fully loaded')
    except NoSuchElementException as e:
        # There was no iframe as part of the post rendering so done since the get()
        # would have waited till page loaded
        logger.error("No iframe used so page must already be fully loaded")
        return


def get_rect(screenshot) -> object:
    """
    Gets the rectangle of the iframe, including 1 px margin around it. The units are
    in screen pixels and can be used to crop screenshot image to just the iframe with
    small border.
    :param screenshot:
    :return:
    """
    logger.info(f'Getting rectangle of iframe...')

    # Make sure that post is first fully loaded
    wait_till_loaded()
    logger.info(f'Waited till html was fully loaded')

    post_element = get_post_element()
    logger.info(f'post_element dom id = {post_element.get_dom_attribute("id")}')

    # Determine dimensions of the element
    ratio = get_image_pixels_per_browser_pixel(screenshot)
    rect = post_element.rect
    left = rect['x'] * ratio - 1
    right = left + (rect['width'] * ratio) + 2
    top = rect['y'] * ratio - 1
    bottom = top + (rect['height'] * ratio) + 2

    return round(left), round(top), round(right), round(bottom)
