# Indicates what type of post dealing with
from enum import Enum


class PostType(Enum):
    XITTER = 1
    THREADS = 2
    BLUESKY = 3
    UNKNOWN = 0
