from fastapi.testclient import TestClient
from unittest.mock import patch
from main import app
from core.config.settings import get_settings

import time

from selenium import webdriver
from selenium.webdriver import FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from pyvirtualdisplay import Display

# Set up environment
settings = get_settings()
URL = f"http://{settings.APP_HOST}:{settings.APP_PORT}"

geckodriver_path = "/usr/local/bin/geckodriver"
service = webdriver.FirefoxService(executable_path = geckodriver_path)

client = TestClient(app)

# Tests

def test_open_home():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]  # Check content type
    assert "Welcome to Splitwise tools!" in response.text  # Verify the HTML contains expected content

def test_login_sw_redirect():
    display = Display(visible=True, size=(1024, 768))
    display.start()

    opts = FirefoxOptions()
    # opts.add_argument("--headless")
    driver = webdriver.Firefox(service = service,options=opts)

    try:
        # Navigate to the FastAPI app's /login_sw route
        driver.get("http://127.0.0.1:8000/login_sw")

        # Allow some time for the page to load and the redirect to occur
        time.sleep(2)

        # After the redirect, check the URL (it should contain the expected pattern)
        current_url = driver.current_url
        assert current_url == "https://www.splitwise.com/login"

        # Enter credentials
        email_input = driver.find_element(By.NAME, "credentials[identity]")  # Adjust if Splitwise uses a different field name
        password_input = driver.find_element(By.NAME, "credentials[password]")  # Adjust if Splitwise uses a different field name

        email_input.send_keys(settings.TEST_USER)  # Replace with a valid test email
        password_input.send_keys(settings.TEST_PASSWORD)  # Replace with a valid test password

        # Allow time for the CAPTCHA to appear (if necessary)
        time.sleep(2)

        # Now you should see the CAPTCHA and can manually solve it.
        print("Please solve the CAPTCHA manually and press Enter to continue...")

        input("Press Enter after solving the CAPTCHA...")

        # Optionally, check for other parameters like 'state' in the URL
        assert "state=fake_state" in current_url, "State parameter not found in the redirect URL"

        print("Test passed! Redirection works as expected.")

    finally:
        # Clean up by closing the browser
        driver.quit()
        display.stop()

# Run the test
test_login_sw_redirect()


