from components.cachebase import CacheBase
from constants.cache import *


class DragonCache(CacheBase):
    def interim(self):
        # run interim stuff if there is a current job
        raise NotImplementedError
