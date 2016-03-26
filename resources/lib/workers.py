# -*- coding: utf-8 -*-
import threading
from helpers import *
import time
import requests
import StringIO

import xbmcaddon
__addon__ = xbmcaddon.Addon()
__scriptname__ = __addon__.getAddonInfo('name')

__url__ = None
__headers__ = {'Content-Type': 'application/octet-stream'}

def take_snapshot(cap, w, h):
  cap.capture(w, h)
  # Only proceed if the capture has succeeded!
  while True:
    cap.waitForCaptureStateChangeEvent(300)
    state = cap.getCaptureState()
    if state == xbmc.CAPTURE_STATE_DONE:
      break
    elif state == xbmc.CAPTURE_STATE_FAILED:
      xbmc.sleep(1000)
      cap.capture(w, h)
      continue

  return cap.getImage()

def led_detect(dev_name):
  url = 'http://%s/bmp' % dev_name

  try:
    res = requests.post(url=url, data=get_start(), headers=__headers__, timeout=2.0)
    if res.status_code == requests.codes.ok and res.text == 'ok !':
      notify(__scriptname__, '%s found %s' % (dev_name, res.text,))
      global __url__
      __url__ = url
  except:
    # Device is not found
    notify(__scriptname__, '%s is not found' % (dev_name,))
    pass

def led_set(data):
    if __url__:
      # Send data to leds
      try:
        res = requests.post(url=__url__, data=data, headers=__headers__, timeout=1.0)
      except:
        log('Error post %s' % __url__)
        pass

def img_proc(w, h, s_w, s_h, rate, dbg_fcnt, alpha, fname, r, g, b, gamma_corr, sat, dev_name, full, stop):
  thr = threading.current_thread()
  cap = xbmc.RenderCapture()
  start_time = None
  mtx = get_rgb2rgb(sat)
  cnt = 0
  vid_stop = False

  if cap.getImageFormat() in ['BGRA', 'RGBA']:
    bpp = 4
  else:
    bpp = 3

  led_detect(dev_name)

  while not stop.is_set():
    if xbmc.Player().isPlayingVideo():
      corr_start = time.time()
      pix = take_snapshot(cap, w * s_w, h * s_h)

      output = StringIO.StringIO()
      img = Image.new( 'RGB', (w, h))
      pixels = img.load()

      for x, y, z, _w, _h in extract_pixes(pix, cap.getWidth(), cap.getHeight(), alpha, full, s_w, s_h, bpp):
        # rgb2rgb
        x1 = clamp(0, x * mtx['rr'] + y * mtx['rg'] + z * mtx['rb'], 255)
        y1 = clamp(0, x * mtx['gr'] + y * mtx['gg'] + z * mtx['gb'], 255)
        z1 = clamp(0, x * mtx['br'] + y * mtx['bg'] + z * mtx['bb'], 255)
        pixels[_w, _h] = (gamma(x1, r, gamma_corr), gamma(y1, g, gamma_corr), gamma(z1, b, gamma_corr))

      #img = led_data.transpose(Image.FLIP_TOP_BOTTOM)
      img.save(output, format='bmp')

      led_set(output.getvalue())

      if not (cnt % dbg_fcnt) and fname:
        if start_time:
          log ('%s %d Fps: %f ' % (thr.name, cnt, (1/((time.time() - start_time)/dbg_fcnt))))
          save_bmp(output.getvalue())
          if not full:
            save_png(bytes(pix), (cap.getWidth(), cap.getHeight()), cap.getImageFormat(), fname)
        start_time = time.time()

      cnt += 1
      vid_stop = True
      output.close()
      xbmc.sleep(max(1, int((rate-(time.time()-corr_start)) * 1000)))
    else:
      if (xbmc.Player().isPlaying() or vid_stop) and __url__:
        vid_stop = False
        try:
          res = requests.post(url=__url__, data=get_start(), headers=__headers__, timeout=1.0)
        except:
          log('Error post %s' % __url__)
          pass
      xbmc.sleep(1000)

  stop.clear()
