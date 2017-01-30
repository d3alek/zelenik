virtualenv -p python3 venv
source venv/bin/activate
pip install -r requirements.txt 

uwsgi --socket 127.0.0.1:3031 --wsgi-file uwsgi.py --master --processes 4 --threads 2 --stats 127.0.0.1:9191 # to generate graphs
