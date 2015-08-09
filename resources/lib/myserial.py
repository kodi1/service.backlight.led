from glob import glob
import os, re
import os.path
from serial import Serial
import sys
from time import sleep
#sudo socat -d -d pty,perm=0666,link=/dev/ttyS41,raw,echo=0 pty,perm=0666,link=/dev/ttyS42,raw,echo=0

class serialLed():
  def __init__(self, speed, timeout):
    cnt_str_match = r'^leds\scnt:\s(\d+)$'
    self.__ser = None
    self.__detected = {
                        'cnt': 0,
                        'name': None,
                      }
    for s in self.__enumerate():
      try:
        self.__ser = Serial(s, speed, timeout=timeout)
        # Wait arduino to reboot
        sleep(3)
        self.__ser.write('00ledc\n')
        sleep(1)
      except:
        continue

      while True:
        l = self.__ser.readline()
        if l:
          m = re.match(cnt_str_match, l)
          if m:
            self.__detected['cnt'] = int(m.group(1))
            self.__detected['name'] = self.__ser.name
        else:
          break

      if self.__detected['name']:
        break
      else:
        self.__ser.close()

  def __del__(self):
    if self.__ser:
      self.__ser.close()

  def detected(self):
    return self.__detected

  def datasend(self, data):
    self.__ser.write(data)

  def datareceive(self):
    lines = []
    while True:
      line = self.__ser.readline()
      if line:
        lines.append(line)
      else:
        return lines

  def __enumerate(self):
    ports = []
    if sys.platform == 'win32':
      # Iterate through registry because WMI does not show virtual serial ports
      import _winreg
      try:
        key = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\DEVICEMAP\SERIALCOMM')
      except WindowsError:
        return []
      i = 0
      while True:
        try:
          ports.append(_winreg.EnumValue(key, i)[1])
          i = i + 1
        except WindowsError:
          break
    elif sys.platform == 'linux2':
      if os.path.exists('/dev/serial/by-id'):
        entries = os.listdir('/dev/serial/by-id')
        dirs = [os.readlink(os.path.join('/dev/serial/by-id', x))
                for x in entries]
        ports.extend([os.path.normpath(os.path.join('/dev/serial/by-id', x))
                    for x in dirs])

      for dev in glob('/dev/ttyS*'):
        try:
          port = Serial(dev)
        except:
          pass
        else:
          ports.append(dev)
    return ports
