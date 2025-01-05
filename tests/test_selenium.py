# Tests that the selenium driver works
import pytest
from selenium import webdriver
from selenium.webdriver import FirefoxOptions

@pytest.mark.selenium
def test_selenium():
    opts = FirefoxOptions()
    opts.add_argument("--headless")
    geckodriver_path = "/usr/local/bin/geckodriver"
    service = webdriver.FirefoxService(executable_path = geckodriver_path)
    browser = webdriver.Firefox(service = service,options=opts)

    browser.get('https://duck.com')

    assert browser.status_code == 200

    browser.quit()