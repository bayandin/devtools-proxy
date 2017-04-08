#!/usr/bin/env ruby

require 'selenium-webdriver'
require 'websocket-client-simple'

require 'json'
require 'net/http'

CHROME_WRAPPER_PATH = '/path/to/chrome-wrapper.sh'
DEVTOOLS_PROXY_PATH = '/path/to/devtools-proxy'
DEVTOOLS_PROXY_PORT = 9222

opts = {
  chromeOptions: {
    binary: CHROME_WRAPPER_PATH,
    args: [
      "--devtools-proxy-binary=#{DEVTOOLS_PROXY_PATH}",
      "--devtools-proxy-args=--port #{DEVTOOLS_PROXY_PORT}"
    ]
  }
}

caps = Selenium::WebDriver::Remote::Capabilities.chrome(opts)
driver = Selenium::WebDriver.for(:chrome, desired_capabilities: caps)

begin
  response = Net::HTTP.get '127.0.0.1', '/json/list', DEVTOOLS_PROXY_PORT
  tab = JSON.parse(response).find { |tab| tab['type'] == 'page' }
  devtools_url = tab['webSocketDebuggerUrl']
  driver.navigate.to 'https://codepen.io/bayandin/full/xRpROy/'

  ws = WebSocket::Client::Simple.connect devtools_url
  data = {
    method: 'Emulation.setCPUThrottlingRate',
    params: {
      rate: 10,
    },
    id: 0,
  }.to_json
  ws.send data
  ws.close
ensure
  driver.quit
end
