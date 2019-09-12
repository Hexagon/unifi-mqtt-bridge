# MIT License
#
# Copyright (c) 2019 Hexagon <Hexagon@GitHub>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from datetime import datetime
import paho.mqtt.publish as publish
import logging
import os
import sys
import time

from unifi_video import UnifiVideoAPI
from datetime import datetime
import pytz

# Read environment
mqtt_host = os.getenv('MQTT_HOST')
mqtt_port = os.getenv('MQTT_PORT', 1883)
mqtt_user = os.getenv('MQTT_USER')
mqtt_pass = os.getenv('MQTT_PASS')
mqtt_topic = os.getenv('MQTT_TOPIC')
nvr_host = os.getenv('NVR_HOST')
nvr_api_key = os.getenv('NVR_API_KEY')
wavemon_logfile = os.getenv('UB_LOGFILE')
ub_interval_s = int(os.getenv('UB_INTERVAL_S','10'))
ub_timezone = os.getenv('UB_TIMEZONE','Europe/Stockholm')
ub_timeformat = os.getenv('UB_TIMEFORMAT','%Y-%m-%d %H:%M:%S')

tz = pytz.timezone(ub_timezone)

lastRecordMemory = {}

# Set up logging
if wavemon_logfile != "None":
	logging.basicConfig(level=logging.DEBUG, filename=wavemon_logfile, filemode='w', format='%(name)s - %(asctime)s - %(levelname)s - %(message)s')
else:
	logging.basicConfig(level=logging.DEBUG)

# Log environment
logging.info("Config: MQTT_HOST resolved to %s", mqtt_host)
logging.info("Config: NVR_HOST resolved to %s", nvr_host)
logging.info("Config: WM_LOGFILE resolved to %s", wavemon_logfile)

if mqtt_host != None:
	logging.info("MQTT publishing enabled")

	# Log extended environment for MQTT
	logging.info("Config: MQTT_PORT resolved to %s", mqtt_port)
	logging.info("Config: MQTT_USER resolved to %s", mqtt_user)
	logging.info("Config: MQTT_PASS resolved to %s", mqtt_pass)
	logging.info("Config: MQTT_TOPIC resolved to %s", mqtt_topic)

def publish_mqtt(msgs):

	mqtt_auth = None
	
	if mqtt_user != None:
		mqtt_auth = {'username':mqtt_user, 'password':mqtt_pass}

	if msgs != None and mqtt_host != None:
		try:
			publish.multiple(msgs, hostname=mqtt_host, port=mqtt_port, client_id="unifimqttbridge", auth=mqtt_auth, tls=None)
		except Exception as ex:
			logging.error('Exception while publishing to MQTT broker: {}'.format(ex))

while True:
	
	start = datetime.now()

	try:
		# Use HTTPS and skip cert verification
		uva = UnifiVideoAPI(api_key=nvr_api_key, addr=nvr_host, port=7443, schema='https', verify_cert=False)
	except Exception as ex:
		logging.error('Exception while communicating with : {}'.format(ex))

	mqtt_msgs = []
			
	for camera in uva.cameras:
		name = camera.name
		lastRecord = camera._data.get('lastRecordingStartTime',None)
		
		if lastRecord != None and lastRecordMemory.get(name,None) != lastRecord:
			lastRecordMemory[name] = lastRecord
			lastRecordReadable = datetime.utcfromtimestamp(lastRecord/1000).replace(tzinfo=pytz.utc).astimezone(tz).strftime(ub_timeformat)
			mqtt_msgs.append((mqtt_topic+'/'+name.lower(),lastRecordReadable,0,False))
			logging.info('Motion detected on %s at %s',name,lastRecordReadable)

	if len(mqtt_msgs) > 0:
		publish_mqtt(mqtt_msgs)

	# Calculate how long time to wait until next round
	diff = datetime.now() - start
	elapsed_ms = (diff.days * 86400000) + (diff.seconds * 1000) + (diff.microseconds / 1000)
	sleep_s = (ub_interval_s)-(elapsed_ms/1000)

	# Never sleep less than 5 seconds between rounds
	if sleep_s < 5:
		sleep_s = 5

	logging.info('Round done, sleeping %fs until next interval.', sleep_s) 
	time.sleep( sleep_s )
