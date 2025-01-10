import hashlib


def stable_hash_str(key: str) -> str:
    """
    A hash function that is consistent across restarts. That is of course important for file names for a cache.
    :param key: string to be hashed.
    :return: a 12 character hex hash string
    """
    str_bytes = bytes(key, "UTF-8")
    m = hashlib.md5(str_bytes)
    return m.hexdigest()[:12].upper()