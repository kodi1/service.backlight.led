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

def m_start(stop_evt):
  # start helper threads
  if __addon__.getSetting('full') == 'true':
    _full = True
  else:
    _full = False

  proc_arg = (
                int(__addon__.getSetting('width')),
                int(__addon__.getSetting('height')),
                int(__addon__.getSetting('w_scale')),
                int(__addon__.getSetting('h_scale')),
                (1.0 / float(__addon__.getSetting('rate'))),
                int(__addon__.getSetting('dbgcnt')),
                50,
                fname,
                int(__addon__.getSetting('rpix')),
                int(__addon__.getSetting('gpix')),
                int(__addon__.getSetting('bpix')),
                float(__addon__.getSetting('gamma')),
                float(__addon__.getSetting('saturation')),
                __addon__.getSetting('host'),
                _full,
                stop_evt,
              )
  t = threading.Thread(target=img_proc, name='img_proc', args=proc_arg)

  # Set threads to exit when main completed
  t.start()
  return t

def m_stop(d, e):
  e.set()
  d.join()

class MyMonitor(xbmc.Monitor):
  def __init__(self, *args, **kwargs):
    xbmc.Monitor.__init__(self)
    self.__evt = threading.Event()
    self.__t = m_start(self.__evt)

  def __del__(self):
    m_stop(self.__t, self.__evt)

  def onSettingsChanged(self):
    m_stop(self.__t, self.__evt)
    self.__t = m_start(self.__evt)

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

  monitor = MyMonitor()

  while True:
    # Sleep/wait for abort for 1 seconds
    if monitor.waitForAbort(1):
      # Abort was requested while waiting. We should exit
      break

  del monitor
