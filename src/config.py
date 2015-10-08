import os


HOST = os.environ.get('HOST', '0.0.0.0')
PORT = int(os.environ.get('PORT', 80))
DEBUG = os.environ.get('DEBUG', 'true').lower() == 'true'

# Results backend configurations
SQLALCHEMY_DATABASE_URI = os.environ['DATABASE_URL']

QUEUE_ENGINE = os.environ.get("QUEUE_ENGINE", "REDIS")

# Redis Queue configurations
REDIS_HOST = os.environ.get('REDIS_HOST', None)
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))

# SQS Queue configurations
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', None)
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', None)
AWS_REGION = os.environ.get('AWS_REGION', None)

SQLALCHEMY_POOL_SIZE = int(os.environ.get("SQLALCHEMY_POOL_SIZE", 10))
SQLALCHEMY_POOL_TIMEOUT = int(os.environ.get("SQLALCHEMY_POOL_TIMEOUT", 30))
SQLALCHEMY_MAX_OVERFLOW = int(os.environ.get("SQLALCHEMY_MAX_OVERFLOW", 20))
