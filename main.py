#
from http.server import ThreadingHTTPServer
import browser
from requestHandler import RequestHandler


def start_webserver():
    """Starts the webserver and then just waits forever"""
    server = ThreadingHTTPServer(('', 8081), RequestHandler)

    # Respond to requests until process is killed
    server.serve_forever()


def run():
    # Get the html for the post specified by thw url
    browser.browser_get('file:///Users/michaelsmith/PycharmProjects/post2image/tweet.html')  #('http://selenium.dev/')

    # Save full screenshot for comparison for debugging
    browser.wait_till_loaded()
    screenshot = browser.get_screenshot()
    screenshot.save('tmp/image.png')

    cropped_screenshot = screenshot.crop(browser.get_rect(screenshot))
    cropped_screenshot.save('tmp/cropped.png')


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    start_webserver()
