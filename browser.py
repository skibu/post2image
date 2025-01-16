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

from bluesky import get_bluesky_likes_str, get_bluesky_post_text, get_bluesky_rect
from main import config_values
from browserType import PostType
from threads import get_threads_likes_str, get_threads_post_text, get_threads_rect
from twitter import get_twitter_likes_str, get_twitter_post_text, get_twitter_rect

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
    _browser.set_window_size(600, 1000)


def _make_modifications(post_type: PostType) -> None:
    """
    Finds the X logo if it is a twitter post and replaces it with a funny old twitter logo.
    Doesn't return until the logo, if found, has been fully replaced and displayed such that
    screenshot can be taken. If not a twitter post then simpily returns
    """
    if post_type != PostType.XITTER:
        return

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
            # Found that got timeout with X for 10 secs so increased to 15 secs
            wait = WebDriverWait(_browser, timeout=15)
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


def _get_post_text(post_type: PostType) -> str:
    match post_type:
        case PostType.XITTER:
            return get_twitter_post_text(_browser)
        case PostType.BLUESKY:
            return get_bluesky_post_text(_browser)
        case PostType.THREADS:
            return get_threads_post_text(_browser)
        case _:
            return ''


def _get_likes_str(post_type: PostType) -> str:
    """
    Examines the HTML and returns string to be displayed showing number of likes.
    :param post_type:
    :return: string that can be displayed indicating number of likes
    """
    match post_type:
        case PostType.XITTER:
            return get_twitter_likes_str(_browser)
        case PostType.BLUESKY:
            return get_bluesky_likes_str(_browser)
        case PostType.THREADS:
            return get_threads_likes_str(_browser)
        case _:
            return ''


def get_screenshot_for_html(url: str, post_type: PostType) -> tuple[Image, float, str, str | None]:
    """
    Loads specified URL into the browser, takes a screenshot of it as a PNG,
    and then returns a cropped version of the screenshot.
    The shrinkage is also returned so the caller can know how tiny the resulting text is and
    whether one want to include the post's text as part of the description in the Open Graph card.
    :param url: url of the file containing the html that describes the post. Can be on localhost.
    :param post_type: whether XITTER, BLUESKY, or THREADS
    :return: properly_sized_image, shrinkage, likes_str, post_text
    """
    logger.info(f'Loading headless browser using html in url={url}')

    # Load specified URL into the browser
    _load_url(url)

    # Wait till html fully loaded, include javascript and iframes
    _wait_till_fully_loaded()

    # Determine how many likes there are
    likes_str = _get_likes_str(post_type)

    # Determine post text in case want to display it via OpenGraph description
    post_text = _get_post_text(post_type)

    # If want to make any modifications to the html, do so now
    _make_modifications(post_type)

    # Take a screenshot of the url content
    screenshot = _get_screenshot()

    # Crop it to remove surrounding white space
    rect = _determine_key_part_of_screenshot(screenshot, post_type)
    cropped_screenshot = screenshot.crop(rect)

    # FIXME For debugging save the images
    screenshot.save('images/debug_orig_image.png')
    cropped_screenshot.save('images/debug_cropped_image.png')

    properly_sized_image = _get_properly_sized_image(cropped_screenshot)
    return (properly_sized_image,
            properly_sized_image.height / cropped_screenshot.height,
            likes_str,
            post_text)


def _get_properly_sized_image(img: Image) -> Image:
    """
    When the important part of the screenshot of the post is generated, it won't have the ideal
    aspect ratio. This can cause Bluesky in particular to display image with clipped off top and
    bottom if the image to aspect ratio is too tall. And it can cut off the left and right sides
    if aspect ratio is too wide. Therefore want to have the resulting image have the proper Bluesky
    aspect ratio, and to do that can simply use the ratio of width of 1200 and  height of 630 for
    a ratio of 1200/630 = 1.9
    :param img: the image of the post
    :return: the image, but with width of 1200 and height of 630
    """
    DESIRED_ASPECT_RATIO = 1.9  # width / height
    img_w, img_h = img.size

    # Determine desired width and height of the final image such that the cropped
    # image fits in it and it has the desired aspect ratio of 1.9
    if img_w / img_h < DESIRED_ASPECT_RATIO:
        # Image too tall so need a larger desired_w
        logger.info(f'For img_w={img_w} img_h={img_h} the image too tall')
        desired_w = DESIRED_ASPECT_RATIO * img_h
        desired_h = img_h
    else:
        # Image too wide so need a larger desired_h
        logger.info(f'For img_w={img_w} img_h={img_h} the image too wide')
        desired_h = img_w / DESIRED_ASPECT_RATIO
        desired_w = img_w
    logger.info(f'Using desired_w={desired_w} and desired_h={desired_h}')

    # If image too large then shrink it down in case the site crops large images even if
    # they have proper aspect ratio
    if desired_w > 1200:
        desired_w = 1200
        desired_h = 630
        logging.info(f'Since desired_w was greater than 1200 setting desired_w={desired_w} desired_h={desired_h}')

    # If image too large then shrink it down to max of width 1200 and height of 630
    if img_w > desired_w or img_h > desired_h:
        shrinkage = min(desired_w / img_w, desired_h / img_h)
        shrunken_size = round(shrinkage * img_w), round(shrinkage * img_h)
        img.thumbnail(shrunken_size, Image.Resampling.LANCZOS)
        img_w, img_h = img.size
        logging.info(f'Shrunk image so it is now img_w={img_w} img_h={img_h}')

    # Create background semi-transparent image that is desired size and the right color.
    # Using values of 31 and transparency of 230 so that in Bluesky the background will
    # simply blend in with the post. Originally thought wanted a low transparency but it
    # turns out thee Bluesky background color is darker than want.
    img_of_proper_size = Image.new(mode="RGBA",
                                   size=(desired_w, desired_h),
                                   color=(31, 31, 31, 230))

    # Write the shrunken image onto center of the transparent background
    centering_offset = ((desired_w - img_w) // 2, (desired_h - img_h) // 2)
    img_of_proper_size.paste(img, centering_offset)

    # Return the shrunken image with transparent sides
    return img_of_proper_size


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
        logger.info(f'An iframe html element found')

        # switch to selected iframe document so can see if its sub-elements are ready
        _browser.switch_to.frame(iframe)

        # Find an element in the iframe that will be displayed once iframe fully loaded.
        # Since the elements in the frame might not have been loaded yet need to
        # give it a few seconds.
        _browser.implicitly_wait(5)
        element = _browser.find_element(By.TAG_NAME, 'div')
        logger.info(f'Found a div html element within the iframe. DOM id= {element.get_dom_attribute("id")}')

        # Wait until the element has actually been displayed
        logger.info(f'Waiting for div element to be displayed...')
        wait = WebDriverWait(_browser, timeout=10)
        wait.until(lambda d: element.is_displayed())
        logger.info(f'div element is now displayed')

        # For some systems it turns out that it can take a while to load in images.
        # Therefore should wait for all of them to load for continuing and taking snapshot.
        logger.info('Making sure all images displayed...')
        image_elements = _browser.find_elements(By.TAG_NAME, 'img')
        wait = WebDriverWait(_browser, timeout=5)
        for image in image_elements:
            # Wait until the DOM element is displayed
            wait.until(lambda d: image.is_displayed())

            # But really want to make sure that the image has actually been loaded, which is_displayed()
            # does not indicate. Therefore execute javascript to determine if the html image element is "complete"
            while True:
                complete = _browser.execute_script("return arguments[0].complete", image)
                if complete:
                    break
            logger.info(f'another one of the images now completely loaded')

        logger.info('The post is now fully loaded, images and all')
    except NoSuchElementException as e:
        # There was no iframe as part of the post rendering so can't wait
        logger.error("No iframe used so page so cannot wait until loaded", e)
        return
    finally:
        # Switch back to the main frame so that subsequent software not confused
        _browser.switch_to.default_content()


def _determine_key_part_of_screenshot(screenshot: Image, post_type: PostType) -> tuple[int, int, int, int]:
    """
    Gets the rectangle of the important part of the post. Want to use the least amount of height
    possible since BlueSky uses fixed aspect ratio for Open Graph cards and if the post is too
    tall then the image is shrunk down too much. The units are in screen pixels
    :param screenshot: an Image to be trimmed
    :param post_type: so different post types can be handled differently
    :return:left, top, right, bottom, the coordinates of the important part of the image that should be kept
    """
    logger.info(f'Getting rectangle of important part of <article> tag...')

    ratio = _get_image_pixels_per_browser_pixel(screenshot)
    logger.info(f'Pixel ratio={ratio}')

    match post_type:
        case PostType.XITTER:
            return get_twitter_rect(ratio, _browser)
        case PostType.BLUESKY:
            return get_bluesky_rect(ratio, _browser)
        case PostType.THREADS:
            return get_threads_rect(ratio, _browser)
        case _:
            return 0, 0, screenshot.width, screenshot.height
