import os
import time
import requests


url = os.environ["URL"]


while True:
    try:
        r = requests.get(url)
    except Exception as e:
        print "ERROR: %s" % e
    time.sleep(5)
