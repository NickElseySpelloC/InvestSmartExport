"""Login to InvestSmart and download the current fund prices listed in the selected watchlist."""

import csv
import json
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import (  # Ensure this is imported
    InvalidSelectorException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as expected_con
from selenium.webdriver.support.ui import WebDriverWait

from utility import ConfigManager, UtilityFunctions

FUND_CODE_CACHE_FILE = "fund_code_cache.json"

# Create an instance of ConfigManager
system_config = ConfigManager()

# Create an instance of the PowerControllerState
utility_funcs = UtilityFunctions(system_config)


def try_login_bypass(web_driver):
    """Attempt to use cookies to skip login. Tries to get the watchlist page."""
    watchlist_url = utility_funcs.config["InvestSmart"]["WatchlistURL"]
    page_load_wait = utility_funcs.config["InvestSmart"]["LongPageLoad"]

    web_driver.get(watchlist_url)  # Load the domain
    if not load_cookies(web_driver):
        utility_funcs.log_message("No cookies found. Proceeding with login.", "debug")
        return False

    # try the watchlist page again with the cookies loaded
    web_driver.get(watchlist_url)  # Navigate to a page that requires authentication

    # Check if login was successful (e.g., by looking for a specific element)
    try:
        WebDriverWait(web_driver, page_load_wait).until(
            expected_con.presence_of_element_located(
                (By.XPATH, "//span[text()='My Account']")
            ),
        )
        utility_funcs.log_message(
            "Login skipped by applying cookies, bypassing login.", "debug"
        )

    except TimeoutException:
        utility_funcs.log_message(
            "Cookies were invalid, proceeding to login.", "detailed"
        )
        return False
    else:
        return True


def save_cookies(web_driver):
    """Save cookies to a file."""
    file_path = utility_funcs.cookie_file

    with Path(file_path).open("w", encoding="utf-8") as file:
        json.dump(web_driver.get_cookies(), file, indent=4)

    utility_funcs.log_message("Cookies saved successfully.", "debug")


def load_cookies(web_driver):
    """Load cookies from a file."""
    file_path = utility_funcs.cookie_file

    try:
        with Path(file_path).open(encoding="utf-8") as file:
            cookies = json.load(file)
            for cookie in cookies:
                web_driver.add_cookie(cookie)

        utility_funcs.log_message("Cookies loaded successfully.", "debug")

    except FileNotFoundError:
        utility_funcs.log_message("No cookies file found.", "debug")
        return False

    else:
        return True


def login(web_driver, username, password):
    """Login to InvestSmart using the provided username and password. Return False if login fails."""
    login_url = utility_funcs.config["InvestSmart"]["LoginURL"]
    page_load_wait = utility_funcs.config["InvestSmart"]["LongPageLoad"]

    # Get the login page
    try:
        # Go to login page
        web_driver.get(login_url)

    except TimeoutException as e:
        utility_funcs.report_fatal_error(
            f"Timeout occurred while trying to load the login page {login_url}: {e}"
        )
        return False

    except WebDriverException as e:
        utility_funcs.report_fatal_error(
            f"General web driver error while trying to load the login page {login_url}: {e}"
        )
        return False

    time.sleep(2)  # Small delay to help page load properly

    # If we are debugging, log any browser console errors
    for entry in web_driver.get_log("browser"):
        utility_funcs.log_message(f"Browser console log entry: {entry}", "debug")

    # Wait until the username field is present
    try:
        WebDriverWait(web_driver, page_load_wait).until(
            expected_con.visibility_of_element_located((By.NAME, "Email")),
        )
    except TimeoutException as e:
        utility_funcs.report_fatal_error(
            f"Timeout after {page_load_wait} seconds occurred while waiting for the Email element on the login page {login_url}: {e}"
        )
        return False

    except WebDriverException as e:
        utility_funcs.report_fatal_error(
            f"General web driver error while while waiting for the Email element on the login page {login_url}: {e}"
        )
        return False

    # Fill in login form
    username_input = web_driver.find_element(By.NAME, "Email")
    password_input = web_driver.find_element(By.NAME, "Password")
    username_input.send_keys(username)
    password_input.send_keys(password)

    # Submit form - hit enter on the password field
    password_input.send_keys(Keys.RETURN)

    # Wait for successful login - we wait until "My Account" span appears
    try:
        WebDriverWait(web_driver, page_load_wait).until(
            expected_con.presence_of_element_located(
                (By.XPATH, "//span[text()='My Account']")
            ),
        )
    except TimeoutException:
        utility_funcs.report_fatal_error(
            f"Timeout after {page_load_wait} seconds occurred while waiting for the My Account element on the next page {login_url}."
        )
        return False

    except WebDriverException:
        utility_funcs.report_fatal_error(
            f"General web driver error while while waiting for the My Account element on the next page {login_url}."
        )
        return False

    # Login was successful
    return True


def get_watchlist_table(web_driver):
    """Navigate to the specified watchlist URL. Returns a table object if successful, otherwise None."""
    watchlist_url = utility_funcs.config["InvestSmart"]["WatchlistURL"]
    page_load_wait = utility_funcs.config["InvestSmart"]["LongPageLoad"]

    try:
        web_driver.get(watchlist_url)

        # Wait for the watchlist table to load
        table_obj = WebDriverWait(web_driver, page_load_wait).until(
            expected_con.presence_of_element_located(
                (By.XPATH, "//table[@data-sortable-name='watchlist']")
            ),
        )

    except TimeoutException as e:
        utility_funcs.report_fatal_error(
            f"Timeout occurred while trying to load the watchlist page {watchlist_url}: {e}"
        )
        return None

    except WebDriverException as e:
        utility_funcs.report_fatal_error(
            f"General web driver error while trying to load the watchlist page {watchlist_url}: {e}"
        )
        return None

    time.sleep(1)  # Small delay to help page load properly
    return table_obj


def load_fund_code_cache():
    """Load the fund code cache as a list of dicts."""
    if Path(FUND_CODE_CACHE_FILE).exists():
        with Path(FUND_CODE_CACHE_FILE).open("r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def save_fund_code_cache(cache):
    """Save the fund code cache as a list of dicts."""
    with Path(FUND_CODE_CACHE_FILE).open("w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


def extract_apir_code(driver, fund_name):
    """
    Extract the APIR code for a fund.

    First, check the cache. If not found, extract from the page and update the cache.
    """
    cache = load_fund_code_cache()
    # Check cache for fund_name
    for entry in cache:
        if entry.get("fund_name") == fund_name and entry.get("apir_code"):
            return entry["apir_code"]

    apir_code = None
    try:
        rows = driver.find_elements(By.XPATH, "//tr")
        for row in rows:
            label_cells = row.find_elements(By.XPATH, "./td/label[@for='Fund_APIRCode']")
            if label_cells:
                tds = row.find_elements(By.TAG_NAME, "td")
                if len(tds) >= 2:
                    apir_code = tds[1].text.strip()
                    break
    except WebDriverException as e:
        utility_funcs.log_message(f"Could not extract APIR code: {e}", "debug")

    # Save to cache if found
    if apir_code:
        cache.append({"fund_name": fund_name, "apir_code": apir_code})
        save_fund_code_cache(cache)
    return apir_code


def extract_fund_data(table_obj):
    """Extract fund data from the watchlist table, including APIR code from each fund's detail page, with caching."""
    local_tz = datetime.now().astimezone().tzinfo
    try:
        headers = table_obj.find_elements(By.XPATH, ".//thead/tr/th")
    except InvalidSelectorException:
        utility_funcs.report_fatal_error(
            "InvalidSelectorException exception when scanning the watchlist table"
        )
        return None
    except WebDriverException:
        utility_funcs.report_fatal_error(
            "General web driver error when scanning the watchlist table"
        )
        return None

    if headers is None:
        utility_funcs.report_fatal_error("Could not find the watchlist table headers.")
        return None

    fund_col_index = None
    price_col_index = None

    for idx, header in enumerate(headers):
        header_text = header.text.strip().lower()
        if "fund" in header_text:
            fund_col_index = idx
        if "current unit price" in header_text:
            price_col_index = idx

    if fund_col_index is None or price_col_index is None:
        utility_funcs.report_fatal_error(
            "Could not find required columns in the watchlist table."
        )
        return None

    today_str = datetime.now(local_tz).strftime("%d/%m/%Y")
    fund_list = []
    rows = table_obj.find_elements(By.XPATH, ".//tbody/tr")
    if rows is None:
        utility_funcs.report_fatal_error(
            "Could not find any rows in the watchlist table."
        )
        return None

    driver = table_obj.parent

    for row in rows:
        try:
            cells = row.find_elements(By.TAG_NAME, "td")
            fund_cell = cells[fund_col_index]
            fund_link = fund_cell.find_element(By.TAG_NAME, "a")
            fund_name = fund_link.text.strip()
            fund_url = fund_link.get_attribute("href")
            price_text = cells[price_col_index].text.strip()
            price_value = float(price_text.replace("$", "").replace(",", "").strip())

            # Try cache first, else open detail page
            apir_code = extract_apir_code(driver, fund_name)
            if not apir_code:
                driver.execute_script("window.open('');")
                driver.switch_to.window(driver.window_handles[1])
                driver.get(fund_url)
                WebDriverWait(driver, 10).until(
                    expected_con.presence_of_element_located((By.CSS_SELECTOR, "table.table-performance"))
                )
                apir_code = extract_apir_code(driver, fund_name)
                driver.close()
                driver.switch_to.window(driver.window_handles[0])

            fund_list.append((apir_code, today_str, fund_name, "AUD", price_value))
        except WebDriverException as e:
            utility_funcs.report_fatal_error(f"Could not parse a row: {e}")

    return fund_list


def save_to_csv(data, file_path):
    """Save the extracted fund data to a CSV file, including APIR code."""
    # Today's date in dd/mm/yyyy format
    local_tz = datetime.now().astimezone().tzinfo
    today_str = datetime.now(local_tz).strftime("%d/%m/%Y")

    # Set the earliest date to be an offset from today using the DaysToSave setting
    days_to_save = utility_funcs.config["Files"]["DaysToSave"] or 30
    earliest_date = datetime.now(local_tz).date() - timedelta(days=days_to_save)

    # ===== Handle existing CSV (read and remove today's rows) =====
    existing_rows = []
    header = ["Symbol","Date","Name","Currency","Price"]
    if Path(file_path).exists():
        with Path(file_path).open(newline="", encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile)
            header = next(reader, None)  # Read the header
            for row in reader:
                if row:
                    row_date = (
                        datetime.strptime(row[1], "%d/%m/%Y")
                        .astimezone(local_tz)
                        .date()
                    )
                    if row_date >= earliest_date and row[0] != today_str:
                        existing_rows.append(row)

    # ===== Write updated CSV =====
    with Path(file_path).open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)

        # Write header
        writer.writerow(header)

        # Write previous rows (without today's duplicates)
        for row in existing_rows:
            writer.writerow(row)

        # Write today's new rows
        for row in data:
            writer.writerow(row)

    return True


if __name__ == "__main__":
    # Setup the Chrome drive options
    chrome_options = Options()
    window_width = random.randint(1000, 2000)
    window_height = random.randint(1000, 2000)
    chrome_options.add_argument(f"--window-size={window_width},{window_height}")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    # Hide the browser window if headless mode is enabled
    if utility_funcs.config["InvestSmart"]["HeadlessMode"]:
        chrome_options.add_argument("--headless")

    utility_funcs.log_message(
        "Starting InvestSmartExport utility with headless mode: "
        + str(utility_funcs.config["InvestSmart"]["HeadlessMode"]),
        "summary",
    )

    # Start WebDriver
    driver = webdriver.Chrome(options=chrome_options)

    try:
        if not try_login_bypass(driver):
            # Cookies unavailable or invalid - we need to login to the website.
            if login(
                driver,
                utility_funcs.config["InvestSmart"]["Username"],
                utility_funcs.config["InvestSmart"]["Password"],
            ):
                # Call this after a successful login
                save_cookies(driver)
            else:
                driver.quit()
                sys.exit(1)

        # Navigate to the watchlist page
        table = get_watchlist_table(driver)
        if table is None:
            driver.quit()
            sys.exit(1)

        fund_data = extract_fund_data(table)
        if fund_data is None:
            driver.quit()
            sys.exit(1)

        csv_file_name = utility_funcs.config["Files"]["OutputCSV"]
        csv_file_path = utility_funcs.config_manager.select_file_location(csv_file_name)
        if not save_to_csv(fund_data, csv_file_path):
            driver.quit()
            sys.exit(1)

    # Catch any unexpected exceptions
    except Exception as e:  # noqa: BLE001
        utility_funcs.report_fatal_error(
            f"An unexpected error occurred while writing: {e}"
        )
        driver.quit()
        sys.exit(1)

    utility_funcs.log_message(
        f"Data extracted and saved to {csv_file_name} successfully.", "summary"
    )

    driver.quit()

    # If the prior run fails, send email that this run worked OK
    if utility_funcs.fatal_error_tracking("get"):
        utility_funcs.log_message(
            "Run was successful after a prior failure.", "summary"
        )
        utility_funcs.send_email(
            "Run recovery",
            "InvestSmartExport run was successful after a prior failure.",
        )
        utility_funcs.fatal_error_tracking("set")
