# For using Chrome browser to convert complicated html to an image
import logging
from io import BytesIO
from typing import Optional

from PIL import Image
from selenium import webdriver
from selenium.common import NoSuchElementException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.wait import WebDriverWait
from main import config_values

logger = logging.getLogger()

# The headless web browser that is used to render the html
_browser: Optional[WebDriver] = None


def _browser_init() -> None:
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


def _make_modifications() -> None:
    """
    Finds the X logo if it is a twitter post and replaces it with a funny old twitter logo.
    Doesn't return until the logo, if found, has been fully replaced and displayed such that
    screenshot can be taken.
    """
    # Need to just look within the iframe
    iframe = _browser.find_element(By.TAG_NAME, "iframe")
    _browser.switch_to.frame(iframe)

    # Find the X logo if it is a twitter post. Then can replace it. There are several svg
    # icons, but by using find_element() get the first one, which is the one desired. And
    # note that there is a bug where can't just find a svg element using "svg". Instead, need
    # to use *[name()='svg'] as described in https://www.inflectra.com/Support/KnowledgeBase/KB503.aspx
    # And most useful XPath documentation is at https://www.w3schools.com/xml/xpath_syntax.asp
    # switch to selected iframe document so can see if its sub-elements are ready
    parent_of_svg_logo_element = _browser.find_element(By.XPATH, "//article/div//a/*[name()='svg']/..")
    if parent_of_svg_logo_element:
        # Replace the HTML of the <a> element with an image of dead twitter bird instead of the ugly X logo.
        # Note: must use https since that is used for the rest of the page
        logger.info(f'Found X logo (most likely) so will try to replace it with something better...')
        image_html = ('<image src="https://robotaxi.news/wp-content/uploads/2025/01/dead_twitter.png" '
                      'name="replacement_logo" width="41" height="38">')
        _browser.execute_script(f"arguments[0].innerHTML = '{image_html}'", parent_of_svg_logo_element)
        logger.info(f'Updated logo html')

        # Wait for the image to be loaded
        # Find an element in the iframe that will be displayed once iframe fully loaded.
        # Since the elements in the frame might not have been loaded yet need to
        # give it a few seconds.
        _browser.implicitly_wait(5)
        image_element = _browser.find_element(By.NAME, 'replacement_logo')
        if image_element:
            logger.info(f'Found the name=replacement_logo image element so will make sure it is displayed...')
            wait = WebDriverWait(_browser, timeout=10)
            wait.until(lambda d: image_element.is_displayed())
            logger.info(f'Image element now displayed')

            # But really want to make sure that the image has actually been loaded, which is_displayed()
            # does not indicate. Therefore execute javascript to determine if the html image element is "complete"
            while True:
                complete = _browser.execute_script("return arguments[0].complete", image_element)
                if complete:
                    break
            logger.info(f'Image element now "complete", which means it has been fully loaded')

    # Switch back to the main frame so that subsequent software not confused
    _browser.switch_to.default_content()


def _get_number_likes() -> Optional[int]:
    """
    Returns number of likes for a tweet. Determines the number by searching XPATH of html
    for what *appears* to be number of likes.
    :return: (int) number of likes, or None if cannot be determined
    """
    # The return value
    number_likes = None

    # Need to just look within the iframe
    iframe = _browser.find_element(By.TAG_NAME, "iframe")
    _browser.switch_to.frame(iframe)

    # Find the html element that contains number of likes
    xpath_str = '//article/div/a/div/span'
    likes_span_element = _browser.find_element(By.XPATH, xpath_str)

    if likes_span_element:
        # Find the likes html <span> element
        try:
            likes_text = _browser.execute_script("return arguments[0].innerText", likes_span_element)
            if likes_text:
                try:
                    number_likes = int(likes_text)
                    logger.info(f'Found the likes element={number_likes}')
                except ValueError:
                    logger.error(f'Found likes text="{likes_text}" but that could not be converted to an integer')
        except NoSuchElementException as e:
            logger.info(f'Could not find the likes <span> element specified by XPATH={xpath_str}')

    # Switch back to the main frame so that subsequent software not confused
    _browser.switch_to.default_content()

    # Could not determine number of likes
    return number_likes


def get_screenshot_for_html(url: str) -> tuple[Image, Optional[int]]:
    """
    Loads specified URL into the browser, takes a screenshot of it as a PNG,
    and then returns a cropped version of the screenshot.
    :param url: url of the file containing the html that describes the post. Can be on localhost.
    :return: resulting image
    """
    logger.info(f'Loading headless browser using html in url={url}')

    # Load specified URL into the browser
    _load_url(url)

    # Wait till html fully loaded, include javascript and iframes
    _wait_till_fully_loaded()

    # Determine how many likes there are
    num_likes = _get_number_likes()

    # If want to make any modifications to the html, do so now
    _make_modifications()

    # Take a screenshot of the url content
    screenshot = _get_screenshot()

    # Crop it to remove surrounding white space
    rect = _determine_key_part_of_screenshot(screenshot)
    cropped_screenshot = screenshot.crop(rect)

    # FIXME For debugging save the images
    screenshot.save('tmp/image.png')
    cropped_screenshot.save('tmp/cropped.png')

    properly_sized_image = _get_properly_sized_image(cropped_screenshot)
    return properly_sized_image, num_likes


def _get_properly_sized_image(img: Image) -> Image:
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


def _load_url(url) -> None:
    """
    Fetches the URL using the browser and waits till the post
    (but not any iframe) is fully loaded
    :param url:
    :return:
    """
    _browser_init()
    _browser.get(url)


def _get_screenshot() -> Image:
    """
    Takes screenshot of visible part of the browser window and returns it as a Pillow Image
    :return:
    """
    logger.info(f'Taking screenshot...')
    png = _browser.get_screenshot_as_png()
    return Image.open(BytesIO(png))


def _get_image_pixels_per_browser_pixel(image: Image):
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


def _wait_till_fully_loaded() -> None:
    """
    Waits till the post html has been fully loaded.
    First need to determine if the post uses an iframe. If it doesn't then the get()
    will have made sure that the post is fully loaded, so all done. But if an iframe
    exists then need to make sure that it has been loaded.
    :return:None
    """
    logger.info(f'Waiting till html fully loaded and rendered...')

    try:
        # Have find_element() return after just 1 second when looking for iframe.
        # Sometimes TTwitter posts might take a bit to convert to iframe. Therefore
        # need to give some time. But don't want to wait too long because some
        # non-Twitter posts might not use an iframe at all and don't want to wait
        # too long for these.
        _browser.implicitly_wait(1)

        # See if iframe is being used. If not then NoSuchElementException will occur
        iframe = _browser.find_element(By.TAG_NAME, "iframe")
        logger.info(f'iframe found. DOM id={iframe.get_dom_attribute("id")}')

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
        wait = WebDriverWait(_browser, timeout=10)
        wait.until(lambda d: element.is_displayed())
        logger.info(f'div element is now displayed...')

        logger.info('The post is now fully loaded')
    except NoSuchElementException as e:
        # There was no iframe as part of the post rendering so can't wait
        logger.error("No iframe used so page so cannot wait until loaded", e)
        return
    finally:
        # Switch back to the main frame so that subsequent software not confused
        _browser.switch_to.default_content()


def _determine_key_part_of_screenshot(screenshot) -> tuple[int, int, int, int]:
    """
    Gets the rectangle of the important part of the post. Want to use least amount of height
    possible since BlueSky uses fixed aspect ratio for Open Graph cards and if the post is too
    tall then the image is shrunk down too much. The units are
    in screen pixels and can be used to crop screenshot image to just the iframe with
    small border.
    :param screenshot:
    :return:left, top, right, bottom
    """
    logger.info(f'Getting rectangle of important part of <article> tga...')

    ratio = _get_image_pixels_per_browser_pixel(screenshot)
    logger.info(f'Pixel ratio={ratio}')

    # Determine the main <article> element
    iframe = _browser.find_element(By.TAG_NAME, 'iframe')

    # Determine left and right of the post
    iframe_rect = iframe.rect
    left = iframe_rect['x'] * ratio - 1
    right = left + (iframe_rect['width'] * ratio) + 2

    _browser.switch_to.frame(iframe)
    article = _browser.find_element(By.TAG_NAME, 'article')
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
    _browser.switch_to.default_content()

    logger.info(f'crop rect is left={left}, top={top}, right={right}, bottom={bottom}')
    return round(left), round(top), round(right), round(bottom)
