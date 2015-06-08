# -*- coding: utf-8 -*-

import os, sys, serial
import re
import time

import xbmc
import xbmcaddon
__addon__ = xbmcaddon.Addon()
__cwd__ = xbmc.translatePath( __addon__.getAddonInfo('path') ).decode('utf-8')
__cwd__ = xbmc.translatePath( __addon__.getAddonInfo('path') ).decode('utf-8')
__icon_msg__ = xbmc.translatePath( os.path.join( __cwd__, 'resources', 'led.png' ) ).decode('utf-8')

from PIL import Image, ImageStat

def notify (msg1, msg2):
  xbmc.executebuiltin((u'Notification(%s,%s,%s,%s)' % (msg1, msg2, '10000', __icon_msg__)).encode('utf-8'))

def log(*msg):
  xbmc.log((u'*** %s' % (msg,)).encode('utf-8'),level=xbmc.LOGNOTICE)

def savetofile (data, name):
  with open(os.path.join(__cwd__, 'resources', 'lib', name), 'wb') as f:
    f.write(data)

def save_png(pix, size, fmt, name):
  img = Image.frombuffer('RGBA', size, pix, 'raw', fmt)
  img.save(os.path.join(__cwd__, 'resources', 'lib', name))

def extract_pixes(pix, w, h, alpha):
  w1 = w-1
  h1 = h-1
  for x in xrange((((w*h1)+w)-1)*4, ((w*h1)-1)*4, -4):
    pix[x+3] = alpha # modify alpha channel
    # print '< ',x
    yield pix[x+0], pix[x+1], pix[x+2]
  for y in xrange((w*(h1-1))*4, (w-1)*4, -w*4):
    # print '^ ', y
    pix[y+3] = alpha # modify alpha channel
    yield pix[y+0], pix[y+1], pix[y+2]
  for x in xrange(0, w*4, 4):
    # print '> ', x
    pix[x+3] = alpha # modify alpha channel
    yield pix[x], pix[x+1], pix[x+2]
  for y in xrange((w+w1)*4, w*h1*4, w*4):
    # print '| ', y
    pix[y+3] = alpha # modify alpha channel
    yield pix[y], pix[y+1], pix[y+2]

def get_rgb2rgb(sat):
  corr = {}
  mtx = {
              'rr': 1.0, 'rg': 0.0, 'rb': 0.0,
              'gr': 0.0, 'gg': 1.0, 'gb': 0.0,
              'br': 0.0, 'bg': 0.0, 'bb': 1.0,
              'roffset': 0.0,
              'goffset': 0.0,
              'boffset': 0.0,
            }

  ks = (2.0 * sat) + 1.0
  s1 = mtx['rr'] + mtx['gr'] + mtx['br']
  s2 = mtx['rg'] + mtx['gg'] + mtx['bg']
  s3 = mtx['rb'] + mtx['gb'] + mtx['bb'];

  corr['rr'] = (mtx['rr'] * ks - mtx['gr'] * sat - mtx['br'] * sat)
  corr['gr'] = (-mtx['rr'] * sat + mtx['gr'] * ks - mtx['br'] * sat)
  corr['br'] = s1 - corr['rr'] - corr['gr']

  corr['rg'] = (mtx['rg'] * ks - mtx['gg'] * sat - mtx['bg'] * sat)
  corr['gg'] = (-mtx['rg'] * sat + mtx['gg'] * ks - mtx['bg'] * sat)
  corr['bg'] = s2 - corr['rg'] - corr['gg']

  corr['rb'] = (mtx['rb'] * ks - mtx['gb'] * sat - mtx['bb'] * sat)
  corr['gb'] = (-mtx['rb'] * sat + mtx['gb'] * ks - mtx['bb'] * sat)
  corr['bb'] = s3 - corr['rb'] - corr['gb']

  return corr

def clamp(minimum, x, maximum):
  return max(minimum, min(x, maximum))

def gamma(pix, col, gamma):
  return int(col * (pix / 255.0) ** gamma)
