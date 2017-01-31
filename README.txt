virtualenv -p python3 venv
source venv/bin/activate
pip install -r requirements.txt # May take a really long time (half an hour) on slow platforms where numpy/matplotlib need to be compiled from source

# mosquitto
# Copy password file in /www/zelenik/secret
sudo cp /www/zelenik/conf/mosquitto.service /usr/lib/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mosquitto
sudo systemctl restart mosquitto

# From now on mosquitto_{sub,pub} -u <username> -P <password>

# mqtt_operator
sudo cp /www/zelenik/conf/mqtt_operator.service /usr/lib/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mqtt_operator 
sudo systemctl restart mqtt_operator

# nginx
sudo cp /www/zelenik/conf/nginx.service /usr/lib/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable nginx 
sudo systemctl restart nginx

# uwsgi
sudo cp /www/zelenik/conf/uwsgi.service /usr/lib/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable uwsgi
sudo systemctl restart uwsgi




