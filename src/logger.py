import logging
import logging.config
import os

LOG_DIR = 'logs'
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

BASIC_LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standardFormatter': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'fileFormatter': {
            'format': '%(asctime)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s',
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'standardFormatter'
        },
        'file': {
            'class': 'logging.FileHandler',
            'level': 'INFO',
            'formatter': 'fileFormatter',
            'filename': os.path.join(LOG_DIR, 'app.log')
        }
    },
    'loggers': {
        'my_app': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        }
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    }
}
