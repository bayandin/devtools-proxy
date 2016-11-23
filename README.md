#  DevTools Proxy

## Usage

#### Standalone (for any language)

* Download & unzip [standalone binary](https://github.com/bayandin/devtools-proxy/releases)
* Use `chrome-wrapper.sh` as a Chrome `binary` in [`ChromeOptions`](https://sites.google.com/a/chromium.org/chromedriver/capabilities#TOC-chromeOptions-object)
* Add `--devtools-proxy-binary=/path/to/devtools-proxy` to `args`  in `ChromeOptions`.

#### Python

`devtools-proxy` pypi package supports only Python 3.5. If you use any other Python version use Standalone package.

```bash
pip3 install -U devtools-proxy
```

```python
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

from devtools.proxy import CHROME_WRAPPER_PATH

capabilities = DesiredCapabilities.CHROME.copy()
capabilities['chromeOptions'] = {
    'binary': CHROME_WRAPPER_PATH,
    'args': [
        '--devtools-proxy-binary=devtools-proxy',
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
