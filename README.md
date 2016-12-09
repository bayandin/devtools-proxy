#  DevTools Proxy

[![Build Status](https://travis-ci.org/bayandin/devtools-proxy.svg?branch=master)](https://travis-ci.org/bayandin/devtools-proxy)
[![PyPI](https://img.shields.io/pypi/v/devtools-proxy.svg)](https://pypi.python.org/pypi/devtools-proxy)
[![GitHub release](https://img.shields.io/github/release/bayandin/devtools-proxy.svg)](https://github.com/bayandin/devtools-proxy/releases/latest)

## Usage

#### Standalone (for any language)

* Download & unzip [standalone binary](https://github.com/bayandin/devtools-proxy/releases/latest)
* Configure [`ChromeOptions`](https://sites.google.com/a/chromium.org/chromedriver/capabilities#TOC-chromeOptions-object):
    * Set path to `chrome-wrapper.sh` as a `binary`. Optional arguments are mentioned in example for Python below
    * Add `--devtools-proxy-binary=/path/to/devtools-proxy` to `args`

#### Python

`devtools-proxy` pypi package supports only Python 3.5. If you use any other Python version use Standalone package.

```bash
pip install -U devtools-proxy
```

```python
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

from devtools.proxy import CHROME_WRAPPER_PATH

capabilities = DesiredCapabilities.CHROME.copy()
capabilities['chromeOptions'] = {
    'binary': CHROME_WRAPPER_PATH,
    'args': [
        '--devtools-proxy-binary=devtools-proxy',
        # Optional arguments:
        # '--chrome-binary=/path/to/chrome/binary', # Path to Chrome/Chromium binary
        # '--devtools-proxy-chrome-debugging-port=some-free-port', # Port which proxy will listen. Default is 12222
        # '--devtools-proxy-args=--additional --devtools-proxy --arguments, # Additional arguments for devtools-proxy from `devtools-proxy --help`
    ],
}
```

## How it works

```
                 +---+
+----------+     | D |   +--------------+
| CLIENT 1 |<--->| E |   |  +-------+   |
+----------+     | V |<---->| TAB 1 |   |
+----------+     | T |   |  +-------+   |
| CLIENT 2 |<--->| O |   |  +-------+ C |
+----------+     | O |<---->| TAB 2 | H |
+----------+     | L |   |  +-------+ R |
| CLIENT 3 |<--->| S |   |            O |
+----------+     |   |   |            M |
                 | P |   |            E |
                 | R |   |  +-------+   |
+----------+     | O |<---->| TAB M |   |
| CLIENT N |<--->| X |   |  +-------+   |
+----------+     | Y |   +--------------+
                 +---+
```
