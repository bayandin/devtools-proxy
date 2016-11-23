import os
from pathlib import Path

PROJECT_DIR = str(Path(__file__, '../../').resolve())
DEVTOOLS_PROXY_PATH = os.environ.get('DEVTOOLS_PROXY_PATH', '{}/devtools/proxy.py'.format(PROJECT_DIR))
CHROME_WRAPPER_PATH = os.environ.get('CHROME_WRAPPER_PATH', '{}/devtools/chrome-wrapper.sh'.format(PROJECT_DIR))
