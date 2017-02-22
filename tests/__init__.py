import os
from pathlib import Path

PROJECT_DIR = str(Path(__file__, '../../').resolve())
DEVTOOLS_PROXY_PATH = os.environ.get('DEVTOOLS_PROXY_PATH', f'{PROJECT_DIR}/devtools/proxy.py')
CHROME_WRAPPER_PATH = os.environ.get('CHROME_WRAPPER_PATH', f'{PROJECT_DIR}/devtools/chrome-wrapper.sh')
