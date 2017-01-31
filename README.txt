virtualenv -p python3 venv
source venv/bin/activate
pip install -r requirements.txt 

# mosquitto
# Copy password file in /www/zelenik/secret
sudo ln -s /www/zelenik/conf/mosquitto.service /usr/lib/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mosquitto
sudo systemctl restart mosquitto

# From now on mosquitto_{sub,pub} -u <username> -P <password>

# nginx
sudo ln -s /www/zelenik/conf/nginx.service /usr/lib/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable nginx 
sudo systemctl restart nginx

# uwsgi
uwsgi --socket 127.0.0.1:3031 --wsgi-file uwsgi.py --master --processes 4 --threads 2 --stats 127.0.0.1:9191 # to generate graphs


