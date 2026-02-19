from .hot_cache import HotCache

hot_cache = HotCache()

# Domain cache services — import these, not hot_cache directly
from . import thread_cache
from . import calendar_cache
