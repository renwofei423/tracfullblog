
import datetime
import threading

#key = threading.Lock()

class cache(object):
    store = {}
    cache_time=datetime.datetime.now()
    lock = threading.RLock()
    
    def __call__(self,attrname,attrvalue=None):
        self.lock.acquire()
        ret = self.get_set(attrname, attrvalue)
        self.lock.release()
        return ret
    def get_set(self, attrname,attrvalue):
        if  not attrvalue:
            if self._checkTime():
                self.store[attrname] = {}
            try:
                return self.store[attrname]
            except:
                return None
        else:
            self.cache_time = datetime.datetime.now()
            self.store[attrname] = attrvalue
            return attrvalue
    def _checkTime(self):
        return (self.cache_time + datetime.timedelta(hours=23)) < datetime.datetime.now()
        # return (self.cache_time + datetime.timedelta(minutes=5)) < datetime.datetime.now()

c = cache()