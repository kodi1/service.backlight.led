# -*- coding: utf-8 -*-
import threading
from helpers import *
import time
import Queue

import xbmcaddon
__addon__ = xbmcaddon.Addon()
__scriptname__ = __addon__.getAddonInfo('name')

def take_snapshot(cap):
  # Only proceed if the capture has succeeded!
  while True:
    cap.waitForCaptureStateChangeEvent(10)
    if cap.getCaptureState() == xbmc.CAPTURE_STATE_DONE:
      break
  return cap.getImage()

def led_ctrl (q, dev_name, timeout, led_count, dbg_fcnt, fname):
  import requests
  cnt = 0
  thr = threading.current_thread()
  start_time = None
  url = 'http://%s/bmp' % dev_name
  headers={'Content-Type': 'application/octet-stream'}

  data_start = get_start();

  res = requests.post(url=url, data=data_start, headers=headers)
  if res.status_code == requests.codes.ok and res.text == 'ok !':
    notify(__scriptname__, '%s found %s' % (dev_name, res.text,))
    detected = True
  else:
    # Device is not found
    notify(__scriptname__, 'Led Device is not found')
    detected = False

  while True:
    # Get new contol data
    try:
      data = q.get(True, 3)
    except Queue.Empty:
      continue

    if detected:
      # Send data to leds
      try:
        res = requests.post(url=url, data=data, headers=headers, timeout=timeout)
      except:
        log('Error post')
        pass
    else:
      log('Skip %s not found' % dev_name)

    while not q.empty():
      # Flush
      q.get()

    if not (cnt % dbg_fcnt) and fname:
      if start_time:
        log ('%s %d Fps: %f ' % (thr.name, cnt, (1/((time.time() - start_time)/dbg_fcnt))))
      start_time = time.time()

    cnt += 1

def img_proc(q, w, h, rate, dbg_fcnt, alpha, fname, r, g, b, gamma_corr, sat):
  import StringIO
  thr = threading.current_thread()
  cap = xbmc.RenderCapture()
  cap.capture(w, h, (xbmc.CAPTURE_FLAG_CONTINUOUS | xbmc.CAPTURE_FLAG_IMMEDIATELY))
  start_time = None
  mtx = get_rgb2rgb(sat)
  cnt = 0

  while True:
    if xbmc.Player().isPlayingVideo():
      corr_start = time.time()
      pix = take_snapshot(cap)

      output = StringIO.StringIO()
      img = Image.new( 'RGB', (cap.getWidth(), cap.getHeight()), 'black')
      pixels = img.load()

      for x, y, z, w, h in extract_pixes(pix, cap.getWidth(), cap.getHeight(), alpha):
        # rgb2rgb
        x1 = clamp(0, x * mtx['rr'] + y * mtx['rg'] + z * mtx['rb'], 255)
        y1 = clamp(0, x * mtx['gr'] + y * mtx['gg'] + z * mtx['gb'], 255)
        z1 = clamp(0, x * mtx['br'] + y * mtx['bg'] + z * mtx['bb'], 255)
        pixels[w, h] = (gamma(x1, r, gamma_corr), gamma(y1, g, gamma_corr), gamma(z1, b, gamma_corr))

      #led_data = led_data.transpose(Image.FLIP_TOP_BOTTOM)
      img.save(output, format='bmp')

      q.put(output.getvalue())
      #save_bmp(output.getvalue())
      output.close()

      if not (cnt % dbg_fcnt) and fname:
        if start_time:
          log ('%s %d Fps: %f ' % (thr.name, cnt, (1/((time.time() - start_time)/dbg_fcnt))))
          save_png(bytes(pix), (cap.getWidth(), cap.getHeight()), cap.getImageFormat(), fname)
        start_time = time.time()

      cnt += 1
      xbmc.sleep(max(1, int((rate-(time.time()-corr_start)) * 1000)))
    else:
      xbmc.sleep(1000)
