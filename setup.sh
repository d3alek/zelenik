sudo cp /www/zelenik/conf/mosquitto.service /usr/lib/systemd/system/ && \
sudo cp /www/zelenik/conf/mqtt_operator.service /usr/lib/systemd/system/ && \
sudo cp /www/zelenik/conf/nginx.service /usr/lib/systemd/system/ && \
sudo cp /www/zelenik/conf/uwsgi.service /usr/lib/systemd/system/ && \
sudo systemctl daemon-reload && \
sudo systemctl enable mosquitto && \
sudo systemctl enable mqtt_operator && \
sudo systemctl enable nginx && \
sudo systemctl enable uwsgi && \
sudo systemctl restart mosquitto && \
sudo systemctl restart mqtt_operator && \
sudo systemctl restart nginx && \
sudo systemctl restart uwsgi



