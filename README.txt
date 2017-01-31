virtualenv -p python3 venv
source venv/bin/activate
pip install -r requirements.txt 

# mosquitto
TODO

# nginx
sudo ln -s /www/zelenik/conf/nginx.service /usr/lib/systemd/system/nginx.service
sudo systemctl daemon-reload
sudo systemctl restart nginx

# uwsgi
uwsgi --socket 127.0.0.1:3031 --wsgi-file uwsgi.py --master --processes 4 --threads 2 --stats 127.0.0.1:9191 # to generate graphs


