import logging

__version__ = "0.21.0rc12"
version = tuple(__version__.split('.'))

logging.getLogger(__name__).addHandler(logging.NullHandler())