#!/usr/bin/python
# -*- coding: utf8 -*-

import os, sys
import datetime, time
from datetime import datetime, timedelta

if __name__ == '__main__':
  import myserial

  with open('cmd.bin', 'rb') as f:
    bin = f.read()

  print bin

  ledctrl = myserial.serialLed(500000, 0.011)
  detected = ledctrl.detected()
  if detected['name']:
    print 'Dev: %(name)s leds: %(cnt)s' % detected
    while True:
      start = time.time()
      ledctrl.datasend(bin)
      print '%s' % ('-'*10)
      for rx in ledctrl.datareceive():
        print rx,
      print 'Time: %f' % (time.time() - start)

