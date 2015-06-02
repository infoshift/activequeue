import os


HOST = os.environ.get('HOST', '0.0.0.0')
PORT = int(os.environ.get('PORT', 80))
DEBUG = os.environ.get('DEBUG', 'true').lower() == 'true'
REDIS_HOST = os.environ.get('REDIS_HOST', None)
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
SQLALCHEMY_DATABASE_URI = os.environ['DATABASE_URL']
