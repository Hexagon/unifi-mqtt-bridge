#  Unifi NVR MQTT Bridge

Dockerized client that reads last motion of each camera on an Unifi NVR, and sends notifications to a MQTT broker.

unifi-video-api by yuppity (https://github.com/yuppity/unifi-video-api) is used and bundled within this repository.


# Development setup

Setup docker and bluez on the host computer, detailed walk through available at https://github.com/Airthings/wave-reader.

Get the code.

```bash
git checkout https://github.com/Hexagon/unifi-mqtt-bridge.git
cd unifi-mqtt-bridge
```

Build docker image

```bash
docker build -q . --tag="unifi-mqtt-bridge"
```

Create docker container

unifi-mqtt-bridge is configured by passing environment variables to the docker container. NVR_HOST, MQTT_HOST and at leasy one of MQTT_TOPIC_* is mandatory for a working setup.

Available environment variables

Variable | Default
--- | ---
NVR_HOST | -
NVR_API_KEY | -
UB_INTERVAL_S | 10
UB_TIMEZONE | Europe/Stockholm
UB_TIMEFORMAT | %Y-%m-%d %H:%M:%S
MQTT_HOST | -
MQTT_PORT | -
MQTT_USER | -
MQTT_PASS | -
MQTT_TOPIC | -

Example container setup

```bash
docker run \
	-d \
	--restart=always \
	-e NVR_HOST=192.168.1.2 \
	-e MQTT_HOST=192.168.1.3 \
	-e UB_INTERVAL_S=10 \
	-e NVR_API_KEY=asdasdasd \
	-e MQTT_TOPIC="sensor/motion" \
	--name="unifi-monitor" \
	unifi-mqtt-bridge
```


## Debug

This assumes you've named your container "unifi-monitor"

```bash
docker logs unifi-monitor
```
