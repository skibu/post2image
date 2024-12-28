# For handling twitter requests
import json

import requests


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