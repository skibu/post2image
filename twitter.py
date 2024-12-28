# For handling twitter requests
import json

import requests


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
    # Get URL that provides HTML for the post. Using twitter's oembed service, which returns
    # a json object with a html member.
    url = (f'https://publish.twitter.com/oembed?' +
           f'url=https://twitter.com/{user_name}/status/{post_id}&hide_thread=false')

    response = requests.get(url)
    json_result = json.loads(response.content)
    return json_result['html']
