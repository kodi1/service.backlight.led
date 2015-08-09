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

def led_ctrl (q, speed, timeout, led_count, dbg_fcnt, fname):
  import myserial
  cnt = 0
  thr = threading.current_thread()
  start_time = None

  ledctrl = myserial.serialLed(speed, timeout)
  detected = ledctrl.detected()

  if detected['name']:
    notify(__scriptname__, 'Dev: %(name)s leds: %(cnt)s' % detected)
    if led_count != detected['cnt']:
      notify(__scriptname__, 'Leds count mismatch %d != %d' % (led_count, detected['cnt']))
  else:
    # Device is not found
    notify(__scriptname__, 'Led Device is not found')

  while True:
    ll = []
    # Get new contol data
    try:
      data = q.get(True, 3)
    except Queue.Empty:
      continue

    # insert header / size / footer
    ll = [0xaa, 0x55]
    ll.extend(list(divmod(len(data), 256)))
    ll.extend(data)
    ll.extend([0x55, 0xaa])

    if detected['name']:
      # Send data to leds
      ledctrl.datasend(ll)
      # Get data from leds
      rcv = ledctrl.datareceive()

    while not q.empty():
      # Flush
      q.get()

    if not (cnt % dbg_fcnt) and fname:
      if start_time:
        log ('%s %d Fps: %f ' % (thr.name, cnt, (1/((time.time() - start_time)/dbg_fcnt))))
        savetofile(bytearray(ll), 'cmd.bin')
      start_time = time.time()
      if detected['name']:
        for line in rcv:
          log(line)
    cnt += 1

def img_proc(q, w, h, rate, dbg_fcnt, alpha, fname, r, g, b, gamma_corr, sat):
  thr = threading.current_thread()
  cap = xbmc.RenderCapture()
  cap.capture(w, h, (xbmc.CAPTURE_FLAG_CONTINUOUS | xbmc.CAPTURE_FLAG_IMMEDIATELY))
  start_time = None
  mtx = get_rgb2rgb(sat)
  cnt = 0

  while True:
    led_data = []

    if xbmc.Player().isPlayingVideo():
      corr_start = time.time()
      pix = take_snapshot(cap)

      for x, y, z in extract_pixes(pix, cap.getWidth(), cap.getHeight(), alpha):
        # rgb2rgb
        x1 = clamp(0, x * mtx['rr'] + y * mtx['rg'] + z * mtx['rb'], 255)
        y1 = clamp(0, x * mtx['gr'] + y * mtx['gg'] + z * mtx['gb'], 255)
        z1 = clamp(0, x * mtx['br'] + y * mtx['bg'] + z * mtx['bb'], 255)

        #gamma and white point
        led_data.append(gamma(z1, b, gamma_corr))
        led_data.append(gamma(y1, g, gamma_corr))
        led_data.append(gamma(x1, r, gamma_corr))

      q.put(led_data)

      if not (cnt % dbg_fcnt) and fname:
        if start_time:
          log ('%s %d Fps: %f ' % (thr.name, cnt, (1/((time.time() - start_time)/dbg_fcnt))))
          save_png(bytes(pix), (cap.getWidth(), cap.getHeight()), cap.getImageFormat(), fname)
        start_time = time.time()

      cnt += 1
      xbmc.sleep(max(1, int((rate-(time.time()-corr_start)) * 1000)))
    else:
      xbmc.sleep(1000)
