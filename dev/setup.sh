sudo cp /www/zelenik/conf/mosquitto.service /lib/systemd/system/ && \
sudo cp /www/zelenik/conf/mqtt_operator.service /lib/systemd/system/ && \
sudo cp /www/zelenik/conf/error_reporter.service /lib/systemd/system/ && \
sudo cp /www/zelenik/conf/nginx.service /lib/systemd/system/ && \
sudo cp /www/zelenik/conf/uwsgi.service /lib/systemd/system/ && \
sudo cp /www/zelenik/conf/enchanter.service /lib/systemd/system/ && \
sudo cp /www/zelenik/conf/uptime_monitor.service /lib/systemd/system/ && \
sudo systemctl daemon-reload && \
sudo systemctl enable mosquitto && \
sudo systemctl enable mqtt_operator && \
sudo systemctl enable error_reporter && \
sudo systemctl enable nginx && \
sudo systemctl enable uwsgi && \
sudo systemctl enable enchanter && \
sudo systemctl enable uptime_monitor && \
sudo systemctl restart mosquitto && \
sudo systemctl restart mqtt_operator && \
sudo systemctl restart error_reporter && \
sudo systemctl restart nginx && \
sudo systemctl restart uwsgi && \
sudo systemctl restart enchanter && \
sudo systemctl restart uptime_monitor



