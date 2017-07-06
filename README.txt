cd /
sudo mkdir www
sudo chown $USER www
cd www
git clone https://www.github.com/d3alek/zelenik
cd zelenik

virtualenv -p python3 venv 
source venv/bin/activate
pip install -r requirements.txt # May take a really long time (half an hour) on slow platforms where numpy/matplotlib need to be compiled from source, uwsgi needs python3-dev on ubuntu

# Python Systemd Bindings

On Ubuntu:
sudo apt-get install libsystemd-dev gcc python3-dev pkg-config

# mosquitto
# Install mosquitto with your package manager
# Copy password file in /www/zelenik/secret
# From now on mosquitto_{sub,pub} -u <username> -P <password>

# mqtt_operator
# nginx
# Install nginx with your package manager
# uwsgi

To setup mosquitto, mqtt_operator, nginx and uwsgi, run

./setup.sh

Then 127.0.0.1 should be accessible but empty. Now arrange for mqtt traffic to reach your host on port 1883

May need to execute the following command for the index page to work

git submodule update --init

uwsgi should run as a separate user (zelenik). On arch:

sudo useradd -m -s /bin/bash otselo
sudo chgrp -R otselo db
sudo chown -R otselo db
sudo chmod -R 774 db

And add your user to otselo...

sudo usermod -a -G otselo <your user>

And add otselo to systemd-journal

sudo usermod -a -G systemd-journal otselo

