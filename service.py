# -*- coding: utf-8 -*-
import os, sys
import re
import time

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
from ga import ga

__addon__ = xbmcaddon.Addon()
__author__ = __addon__.getAddonInfo('author')
__scriptid__ = __addon__.getAddonInfo('id')
__scriptname__ = __addon__.getAddonInfo('name')
__version__ = __addon__.getAddonInfo('version')
__icon__ = __addon__.getAddonInfo('icon').decode('utf-8')
__language__ = __addon__.getLocalizedString
__cwd__ = xbmc.translatePath( __addon__.getAddonInfo('path') ).decode('utf-8')
__profile__ = xbmc.translatePath( __addon__.getAddonInfo('profile') ).decode('utf-8')
__resource__ = xbmc.translatePath( os.path.join( __cwd__, 'resources', 'lib' ) ).decode('utf-8')

sys.path.insert(0, __resource__)
from workers import *

if __name__ == '__main__':

  if __addon__.getSetting('firstrun') == 'true':
    __addon__.openSettings()
    __addon__.setSetting('firstrun', 'false')

  if __addon__.getSetting('dbg') == 'true':
    fname = 'dbg.png'
  else:
    fname = None

  payload = {}
  payload['an'] = __scriptname__
  payload['av'] = __version__
  payload['ec'] = 'led_start'
  payload['ea'] = 'led_start'
  payload['ev'] = '1'
  ga().update(payload, None)

  monitor = xbmc.Monitor()
  # start helper threads
  queue = Queue.LifoQueue(maxsize=5)
  led_arg = (
              queue,
              int(__addon__.getSetting('speed')),
              (float(__addon__.getSetting('timeout')) / 1000.0),
              (2 * int(__addon__.getSetting('width'))) + (2 * int(__addon__.getSetting('height'))),
              int(__addon__.getSetting('dbgcnt')),
              fname,
            )
  ctrl = threading.Thread(target=led_ctrl, name='ctrl', args=led_arg)

  proc_arg = (
                queue,
                int(__addon__.getSetting('width')),
                int(__addon__.getSetting('height')),
                (1.0 / float(__addon__.getSetting('rate'))),
                int(__addon__.getSetting('dbgcnt')),
                50,
                fname,
                int(__addon__.getSetting('rpix')),
                int(__addon__.getSetting('gpix')),
                int(__addon__.getSetting('bpix')),
                float(__addon__.getSetting('gamma')),
                float(__addon__.getSetting('saturation')),
              )
  img_proc  = threading.Thread(target=img_proc, name='img_proc', args=proc_arg)

  # Set threads to exit when main completed
  ctrl.setDaemon(True)
  img_proc.setDaemon(True)
  ctrl.start()
  img_proc.start()

  while True:
    # Sleep/wait for abort for 3 seconds
    if monitor.waitForAbort(3):
      # Abort was requested while waiting. We should exit
      break
