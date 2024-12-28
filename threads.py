# For handling threads requests
import json

import requests


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

