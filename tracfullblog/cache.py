
import datetime,time
import fcntl
import cPickle,os

#linux default save  in /dev/shm/


class cache(object):
    store = {}   
    SAVE_DIR='/dev/shm/'
    
    
    def __call__(self,attrname,attrvalue=None): 
        ret = self.get_set(attrname, attrvalue)        
        return ret
    def get_set(self, attrname,attrvalue):
        FILE_NAME=self.SAVE_DIR+str(attrname)
        if  not attrvalue:
#            print "not attrvalue!"
            if not self._checkTime(FILE_NAME):
#                self.store[attrname] = {}                
                os.remove(FILE_NAME)
#                print "Time is over!"
            try:
                #get value
                if os.path.exists(FILE_NAME):
#                    print "Get "+str(attrname)+" value!"               
                    fp = open(FILE_NAME,'rb')
#                    print "fp:",
#                    print fp
#                    fp.seek(0)
                    
                    self.store[attrname]=cPickle.load(fp)    
#                    c=cPickle.load(fp)   
#                    print "Get "+str(attrname)+" value done!"
                    return self.store[attrname]
#                    return c
                else:
#                    print "os.path.exists is False!"
                    return None
            except Exception, error:
#                print "~~~~~~~~~~~~~~~~~"
                print error
#            except:     
                return None               
#                
                
        else:
#            print "attrvalue is there! attrvalue: ...",
#            print attrvalue
            
            self.store[attrname] = attrvalue
            
            #set value
            
            fp=open(FILE_NAME,'wrb')
            fcntl.flock(fp,fcntl.LOCK_EX)
            cPickle.dump(self.store[attrname], fp,0)
#            print "dump "+str(attrname)+" to "+FILE_NAME+"!"
            fcntl.flock(fp,fcntl.LOCK_UN)            
            return attrvalue
        
    def _checkTime(self,filename):
        if os.path.exists(filename):
            return (time.time() - 3600*23 < os.path.getmtime(filename) < time.time() + 3600*23)
        else:
            return True


c = cache()