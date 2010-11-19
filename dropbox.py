#!/usr/bin/env python
import os, sys, subprocess, pyinotify
from threading import Timer

class HandleEvents(pyinotify.ProcessEvent):
    timers = {}
    processing = 0
    sync_again = 0
    def process_IN_CREATE(self, event):
        self.changeDetected(event.pathname)
    def process_IN_DELETE(self, event):
        self.changeDetected(event.pathname)
    def process_IN_CLOSE_WRITE(self, event):
        self.changeDetected(event.pathname)
    def process_IN_MODIFY(self, event):
        self.changeDetected(event.pathname)
    def process_IN_MOVED_FROM(self, event):
        self.changeDetected(event.pathname)
    def process_IN_MOVED_TO(self, event):
        self.changeDetected(event.pathname)
    def changeDetected(self, path):
        if path.find('.getempty') >= 0:
            #print "Empty dir, ignore: "+path
            return 0
        if self.processing == 1:
            #print "Inoring change, sync in progress"
            self.sync_again = 1
            return 0
        if 'sync' in self.timers:
            self.timers['sync'].cancel()
        #print "Change detected, not pulling: "+path
        self.timers['sync'] = Timer(10, self.doSync, ())
        self.timers['sync'].start()
    def doSync(self):
        print "DOING SYNC NOW!"
        self.processing = 1
        self.touchEmpty()
        output = os.popen("/opt/get/bin/git status --short").read().strip()
        if len(output) > 0:
            os.system("/opt/get/bin/git add .")
            os.popen("/opt/get/bin/git commit -a -m 'dropbox sync'").read()
            self.rmGetEmpty()
            os.system("/opt/get/bin/git push origin master")
            print "CHANGES COMMITTED:"
            print output
        else:
            self.rmGetEmpty()
            print "CLEAN DROPBOX -- NOTHING TO COMMIT"
        self.syncComplete()
    def syncComplete(self):
        if self.sync_again == 1:
            self.sync_again = 0
            self.doSync()
        else:
            self.sync_again = 0
            self.processing = 0
    def touchEmpty(self):
        os.system("find . -type d -empty -not -wholename ./.get\* -print0 | xargs -0 -I xxx touch xxx/.getempty")
    def rmGetEmpty(self):
        os.system("find . -name '.getempty' -print0 | xargs -0 rm 2>/dev/null")
    def getChanges(self):
        if self.processing == 1:
            if 'pull' in self.timers:
                self.timers['pull'].cancel()
            self.timers['pull'] = Timer(10, self.getChanges, ())
            self.timers['pull'].start()
            return 0;

        self.processing = 1
        commit1 = os.popen("/opt/get/bin/git rev-parse HEAD").read().strip()
        os.system("/opt/get/bin/git pull origin master")
        commit2 = os.popen("/opt/get/bin/git rev-parse HEAD").read().strip()
        if commit1 != commit2:
            output = os.popen("/opt/get/bin/git diff --summary " + commit1 + " " + commit2).read().strip()
            print output
            mylist = output.split("\n")
            for x in mylist:
                rmdir = ''
                if((x.find('delete mode') >= 0) and (x.find('.getempty') >= 0)):
                    x = x.strip()
                    x = x.split(' ')
                    x.pop(0)
                    x.pop(0)
                    x.pop(0)
                    rmdir = ' '.join(x)
                if rmdir.find('.getempty') >= 0:
                    # we _could_ make sure .getempty is the trailing file name
                    rmdir = rmdir.replace('/.getempty','')
                    rmdir = rmdir.replace(' ','\ ')
                    tree = rmdir.split('/')
                    thispath = '/'.join(tree)
                    while not os.listdir(thispath) and len(thispath) > 0:
                        print '**** rmdir: '+thispath
                        os.system('rmdir '+thispath)
                        tree.pop(-1)
                        thispath = '/'.join(tree)
        self.syncComplete()
        if 'pull' in self.timers:
            self.timers['pull'].cancel()
        self.timers['pull'] = Timer(10, self.getChanges, ())
        self.timers['pull'].start()

pyinotify.log.setLevel(50)
path = sys.argv[1]
os.chdir(path)
p = HandleEvents()
p.getChanges()
p.doSync()
wm = pyinotify.WatchManager()
notifier = pyinotify.Notifier(wm, p)
excl_list = [path + '/.get*']
excl = pyinotify.ExcludeFilter(excl_list)
wm.add_watch(path, pyinotify.ALL_EVENTS, rec=True, auto_add=True, exclude_filter=excl)
notifier.loop()
