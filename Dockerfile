FROM alpine:3.7
RUN apk update
RUN apk add python3 py3-pip
RUN mkdir /unifi-mqtt-bridge
COPY src/ /unifi-mqtt-bridge/
COPY entrypoint.sh /docker-entrypoint.sh
RUN ["chmod", "+x", "/docker-entrypoint.sh"]
RUN pip3 install --upgrade pip
RUN pip3 install paho-mqtt pytz
ENTRYPOINT ["/docker-entrypoint.sh"]
