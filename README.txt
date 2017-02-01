cd /
sudo mkdir www
sudo chown $USER www
cd www
git clone https://www.github.com/d3alek/zelenik
cd zelenik

virtualenv -p python3 venv 
source venv/bin/activate
pip install -r requirements.txt # May take a really long time (half an hour) on slow platforms where numpy/matplotlib need to be compiled from source, uwsgi needs python3-dev on ubuntu

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

