import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import pandas as pd
from dotenv import load_dotenv
import os
import re
import glob
import logging

load_dotenv()  # take environment variables from .env.


def create_session():
    """
    Create a requests.Session with a larger connection pool and retry mechanism.
    """
    session = requests.Session()
    adapter = HTTPAdapter(
        pool_connections=20,  # Increase pool size
        pool_maxsize=20,      # Max connections in the pool
        max_retries=Retry(total=3, backoff_factor=1)  # Retry failed requests
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def setup_driver_with_cookie_header(cookie_header):
    """
      Set up the WebDriver with cookies from a raw cookie header string.

      Args:
          cookie_header (str): The raw cookie header string (e.g., "name1=value1; name2=value2").

      Returns:
          WebDriver: The Selenium WebDriver instance with cookies set.
      """
    # Initialize the WebDriver (Chrome in this case).
    driver = webdriver.Chrome()

    # Load a placeholder URL to set cookies (e.g., the base domain).
    placeholder_url = os.environ['PLACEHOLDER_URL']
    driver.get(placeholder_url)

    # Parse and set cookies from the provided header.
    for cookie_entry in cookie_header.split(";"):
        cookie_parts = cookie_entry.split("=", 1)
        # Ensure both name and value are present.
        if len(cookie_parts) == 2:
            name = cookie_parts[0].strip()
            value = cookie_parts[1].strip()
            driver.add_cookie({"name": name, "value": value})

    driver.refresh()  # Reload the page to apply cookies globally.
    return driver


def wait_for_element(driver, class_name, timeout=10):
    try:
        wait = WebDriverWait(driver, timeout)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, class_name)))
        return True
    except TimeoutException:
        return False


def main():
    file_location = "file.xlsx"
    sheet = pd.read_excel(
        file_location, sheet_name="News PK", usecols="A, S").dropna()
    media_headers = {
        "media-full-l": "FULL width header",
        "media-inside": "Rectangle no overlap",
        "bar": "Blue bar",
        "without-media-news": "Text only news",
    }

    cookie_header = os.environ['COOKIE_CONSENT']
    driver = setup_driver_with_cookie_header(cookie_header)

    results = []

    # Create a reusable session
    session = create_session()

    try:
        for _, row in sheet.iterrows():
            docid, template = row['docid'], row['template']
            url = f"https://{os.environ['UNICC_AUTH']
                             }@drupalandia.unhcr.info/pk/{docid}"

            try:
                # Use the session for HTTP requests
                response = session.head(url, allow_redirects=True)
                if response.status_code == 200:
                    file = glob.glob(f"**/*{docid}*", recursive=True)[0]
                    with open(file, 'r') as f:
                        content = f.read()
                    driver.get(url)  # Navigate to the URL
                    # Perform processing logic
                    element = driver.find_element(By.CLASS_NAME, "show-icon")
                    classes = element.get_attribute("class").split()

                    imported_header = classes[5] if len(classes) > 5 else None
                    # If template is full and it's not found
                    if template == "FULL" and not wait_for_element(driver, "media-full-l"):
                        logging.info(
                            f"FULL not exported correctly for {docid}")
                        results.append((docid, media_headers.get(
                            imported_header), media_headers.get("media-full-l")))
                    elif template == "BLACK" and re.search(r"^(<header\b[^>]*>.*?</header>|<p\b[^>]*>\s*<image\b[^>]*>.*?</p>)", content, re.DOTALL):
                        if not wait_for_element(driver, "media-inside"):
                            logging.error(
                                f"Issue with Rectangle No Overlap template for {docid}")
                            results.append((docid, media_headers.get(
                                imported_header), media_headers.get("media-inside")))

                    elif template == "BLACK" and not re.search(r"^(<header\b[^>]*>.*?</header>|<p\b[^>]*>\s*<image\b[^>]*>.*?</p>)", content, re.DOTALL):
                        if not wait_for_element(driver, "without-media-news"):
                            logging.error(
                                f"Issue with News Bar import for {docid}")
                            results.append((docid, media_headers.get(
                                imported_header), media_headers.get("without-media-news")))
            except Exception as e:
                logging.error(f"Error processing {url}: {e}")
    # except Exception as e:
    #     logging.error(f"Error processing : {e}")
    finally:
        driver.quit()
        session.close()  # Ensure the session is properly closed

    return results


def save_to_excel(data, filename="News-pages-with-issues-7.xlsx"):
    columns = ["Docid", "Imported Header", "Correct Header"]
    df = pd.DataFrame(data=data, columns=columns)
    df.to_excel(filename, index=False)
    print(f"Data saved to {filename}")


if __name__ == "__main__":
    data = main()
    if data:
        save_to_excel(data)
    else:
        print("No page without header")
