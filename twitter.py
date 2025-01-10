# For handling twitter requests
import json
import logging
from json import JSONDecodeError

import requests

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
