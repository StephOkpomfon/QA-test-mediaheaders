from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import pandas as pd
import requests
from dotenv import load_dotenv
import os
import re
import glob

load_dotenv()  # take environment variables from .env.


def setup_driver_with_cookie_header(url, cookie_header):
    """
    Set up the WebDriver with cookies from a raw cookie header string.

    Args:
        url (str): The URL to load.
        cookie_header (str): The raw cookie header string (e.g., "name1=value1; name2=value2").

    Returns:
        WebDriver: The Selenium WebDriver instance.
    """
    driver = webdriver.Chrome()
    driver.get(url)

    # Parse and set cookies
    for cookie_entry in cookie_header.split(";"):
        cookie_parts = cookie_entry.split("=", 1)
        if len(cookie_parts) == 2:
            name = cookie_parts[0].strip()
            value = cookie_parts[1].strip()
            driver.add_cookie({"name": name, "value": value})

    driver.refresh()  # Reload the page to apply cookies
    return driver


def main():
    file_location = "file.xlsx"

    # Insert excel file in this folder
    sheet = pd.read_excel(
        file_location, sheet_name="Landing Page PH", usecols="A, X")
    pages_with_issues = []
    data = []

    media_headers = {
        "media-full-l": "FULL width header",
        "media-inside": "Rectangle no overlap",
        "bar": "Blue bar",
        "without-media-news": "Text only news",
    }

    # Iterate through rows and stop at the first row with NaN
    # for _, row in sheet.iloc[1:].iterrows():  # Skip the first row (index 0)
    for _, row in sheet.iterrows():  # Include all rows if headers are correct
        if row.isnull().any():  # Stop if any value in the row is NaN
            break

        docid = row['docid']
        template = row['template']
        print(docid)

        url = f"https://{os.environ['UNICC_AUTH']
                         }@drupalandia.unhcr.info/ph/{docid}"

        try:
            # Check if the URL is valid by making an HTTP request
            response = requests.head(url, allow_redirects=True)
            if response.status_code == 200:  # URL is valid
                # Searches all subdirectories
                file = glob.glob(f"**/*{docid}*", recursive=True)[0]
                with open(file, 'r') as f:
                    content = f.read()

                cookie_header = os.environ['COOKIE_CONSENT']
                driver = setup_driver_with_cookie_header(url, cookie_header)

                element = driver.find_element(
                    By.CLASS_NAME, "show-icon")
                # Get 6th class or None print(sixth_class)

                classes = element.get_attribute("class").split()

                # The imported media header type
                imported_header = classes[4] if len(classes) > 5 else None
                if template == "FULL":
                    # driver.find_element(By.CLASS_NAME, 'media-full-l')

                    try:
                        # Wait up to 10 seconds
                        wait = WebDriverWait(driver, 10)
                        wait.until(EC.presence_of_element_located(
                            (By.CLASS_NAME, "media-full-l")))
                        # Move this from found header to no header after testing
                        print("FULL exported correctly")

                    except TimeoutException:
                        print("FULL not exported correctly")
                        pages_with_issues.append(docid)
                        data.append((docid, media_headers.get(
                            imported_header), media_headers.get("media-full-l")))
                elif template == "BLACK" and re.search(r"<header\b[^>]*>.*?</header>", content, re.DOTALL):

                    try:
                        # Wait up to 10 seconds
                        wait = WebDriverWait(driver, 10)
                        wait.until(EC.presence_of_element_located(
                            (By.CLASS_NAME, "media-inside")))

                        # Move this from found header to no header after testing
                        print("TXMD imported correctly")

                    except TimeoutException:
                        print("TXML not imported correctly")

                    data.append((docid, media_headers.get(
                                imported_header), media_headers.get("media-inside")))

                elif template == "BLACK" and not re.search(r"<header\b[^>]*>.*?</header>", content, re.DOTALL):

                    try:
                        # Wait up to 10 seconds
                        wait = WebDriverWait(driver, 10)
                        wait.until(EC.presence_of_element_located(
                            (By.CLASS_NAME, "bar")))
                        # Move this from found header to no header after testing
                        print("news bar imported correctly")

                    except TimeoutException:
                        print("news bar not imported correctly")
                    data.append((docid, media_headers.get(
                        imported_header), media_headers.get("bar")))

        except (requests.exceptions.RequestException, TimeoutException) as e:
            print(f"Skipping URL {url} due to error: {e}")
            continue  # Proceed to next URL
        finally:
            if 'driver' in locals():
                driver.quit()
    return data


def save_to_excel(data, filename="Landing-pages-with-issues.xlsx"):
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
