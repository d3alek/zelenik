sudo cp /www/zelenik/conf/mosquitto.service /lib/systemd/system/ && \
sudo cp /www/zelenik/conf/mqtt_operator.service /lib/systemd/system/ && \
sudo cp /www/zelenik/conf/error_reporter.service /lib/systemd/system/ && \
sudo cp /www/zelenik/conf/zelenik_nginx.service /lib/systemd/system/ && \
sudo cp /www/zelenik/conf/uwsgi.service /lib/systemd/system/ && \
sudo cp /www/zelenik/conf/enchanter.service /lib/systemd/system/ && \
sudo cp /www/zelenik/conf/uptime_monitor.service /lib/systemd/system/ && \
sudo cp /www/zelenik/conf/server_operator.service /lib/systemd/system/ && \
sudo cp /www/zelenik/conf/rest_uwsgi.service /lib/systemd/system/ && \
sudo systemctl daemon-reload && \
sudo systemctl enable mosquitto && \
sudo systemctl enable mqtt_operator && \
sudo systemctl enable error_reporter && \
sudo systemctl enable zelenik_nginx && \
sudo systemctl enable uwsgi && \
sudo systemctl enable rest_uwsgi && \
sudo systemctl enable enchanter && \
sudo systemctl enable uptime_monitor && \
sudo systemctl enable server_operator && \
sudo systemctl restart mosquitto && \
sudo systemctl restart mqtt_operator && \
sudo systemctl restart error_reporter && \
sudo systemctl restart zelenik_nginx && \
sudo systemctl restart uwsgi && \
sudo systemctl restart rest_uwsgi && \
sudo systemctl restart enchanter && \
sudo systemctl restart uptime_monitor && \
sudo systemctl restart server_operator 



