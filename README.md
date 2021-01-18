# Commands

## virtual environment

python3 -m venv env
source env/bin/activate
pip install -r requirements.txt

## run server

gunicorn -w 4 main:app

visit http://www.localhost:8000