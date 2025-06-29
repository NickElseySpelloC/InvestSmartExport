"""Login to InvestSmart and download the current fund prices listed in the selected watchlist."""

import csv
import json
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from sc_utility import SCConfigManager, SCLogger
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

from config_schemas import ConfigSchema

CONFIG_FILE = "config.yaml"
COOKIE_FILE = "cookies.json"
FUND_CODE_CACHE_FILE = "fund_code_cache.json"


def create_undetectable_chrome(config):
    """Create an undetectable Chrome WebDriver instance with randomized window size and user-agent.

    Args:
        config: The configuration manager instance.

    Returns:
        webdriver.Chrome: An undetectable Chrome WebDriver instance.
    """
    # Set up Chrome options
    chrome_options = Options()

    # Randomize window size
    window_width = random.randint(1000, 2000)
    window_height = random.randint(1000, 2000)
    chrome_options.add_argument(f"--window-size={window_width},{window_height}")

    # General options
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    # Set a realistic user-agent
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )

    if config.get("InvestSmart", "HeadlessMode"):
        chrome_options.add_argument("--headless=new")  # Use newer headless mode

    # Launch driver
    driver = webdriver.Chrome(options=chrome_options)

    # Remove 'navigator.webdriver' flag
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": """
            Object.defineProperty(navigator, 'webdriver', {
              get: () => undefined
            });
            """
        },
    )
    return driver


def try_login_bypass(config, logger, web_driver) -> bool:
    """Attempt to use cookies to skip login. Tries to get the watchlist page.

    Args:
        config: The configuration manager instance.
        logger: The logger instance.
        web_driver: The Selenium WebDriver instance.

    Returns:
        bool: True if login was successful or cookies were valid, False otherwise.
    """
    watchlist_url = config.get("InvestSmart", "WatchlistURL")
    page_load_wait = config.get("InvestSmart", "LongPageLoad")

    web_driver.get(watchlist_url)  # Load the domain
    if not load_cookies(config, logger, web_driver):
        logger.log_message("No cookies found. Proceeding with login.", "debug")
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
        logger.log_message(
            "Login skipped by applying cookies, bypassing login.", "debug"
        )

    except TimeoutException:
        save_cookies()
        logger.log_message(
            "Cookies were invalid, proceeding to login.", "detailed"
        )
        return False
    else:
        return True


def save_cookies(config, logger, web_driver):
    """Save cookies to a file.

    Args:
        config: The configuration manager instance.
        logger: The logger instance.
        web_driver: The Selenium WebDriver instance.
    """
    file_path = config.select_file_location(COOKIE_FILE)

    with file_path.open("w", encoding="utf-8") as file:
        json.dump(web_driver.get_cookies(), file, indent=4)

    logger.log_message("Cookies saved successfully.", "debug")


def load_cookies(config, logger, web_driver) -> bool:
    """Load cookies from a file.

    Args:
        config: The configuration manager instance.
        logger: The logger instance.
        web_driver: The Selenium WebDriver instance.

    Returns:
        bool: True if cookies were loaded successfully, False if no cookies file was found.
    """
    file_path = config.select_file_location(COOKIE_FILE)

    if not file_path.exists():
        return False  # No cookies file found

    try:
        with file_path.open(encoding="utf-8") as file:
            cookies = json.load(file)
            for cookie in cookies:
                web_driver.add_cookie(cookie)

        logger.log_message("Cookies loaded successfully.", "debug")

    except FileNotFoundError:
        logger.log_message("No cookies file found.", "debug")
        return False

    else:
        return True


def delete_cookies(config):
    """Delete the cookies file.

    Args:
        config: The configuration manager instance.
    """
    config.select_file_location(COOKIE_FILE).unlink(missing_ok=True)


def login(config, logger, web_driver, username, password) -> bool:  # noqa: PLR0915
    """Login to InvestSmart using the provided username and password. Return False if login fails.

    Args:
        config: The configuration manager instance.
        logger: The logger instance.
        web_driver: The Selenium WebDriver instance.
        username: The username for login.
        password: The password for login.

    Returns:
        bool: True if login was successful, False otherwise.
    """
    login_url = config.get("InvestSmart", "LoginURL")
    page_load_wait = config.get("InvestSmart", "LongPageLoad")
    short_load_wait = config.get("InvestSmart", "ShortPageLoad")
    login_timeout = False

    # Get the login page
    try:
        # Go to login page
        web_driver.get(login_url)

    except TimeoutException as e:
        logger.log_fatal_error(
            f"Timeout occurred while trying to load the login page {login_url}: {e}"
        )
        return False

    except WebDriverException as e:
        logger.log_fatal_error(
            f"General web driver error while trying to load the login page {login_url}: {e}"
        )
        return False

    time.sleep(2)  # Small delay to help page load properly

    # If we are debugging, log any browser console errors
    for entry in web_driver.get_log("browser"):
        logger.log_message(f"Browser console log entry: {entry}", "debug")

    # Wait until the username field is present
    try:
        WebDriverWait(web_driver, page_load_wait).until(
            expected_con.visibility_of_element_located((By.NAME, "Email")),
        )
    except TimeoutException:
        # If we get a timeout waitiing for the email element on the login page, it's possible that we have been logged in already
        login_timeout = True

    except WebDriverException as e:
        logger.log_fatal_error(
            f"General web driver error while while waiting for the Email element on the login page {login_url}: {e}"
        )
        return False

    # If we have a login time, first check to see if we're on the account page
    if login_timeout:
        try:
            WebDriverWait(web_driver, short_load_wait).until(
                expected_con.presence_of_element_located(
                    (By.XPATH, "//span[text()='My Account']")
                ),
            )
            logger.log_message(
                "Login skipped by applying cookies, bypassing login.", "debug"
            )

        except TimeoutException:
            logger.log_fatal_error(
                f"Timeout after {page_load_wait} seconds occurred while waiting for the Email element on the login page {login_url}"
            )
            return False
        else:
            return True  # Already logged in, so return True

    # Fill in login form
    username_input = web_driver.find_element(By.NAME, "Email")
    password_input = web_driver.find_element(By.NAME, "Password")
    username_input.send_keys(username)
    password_input.send_keys(password)

    # Submit the form - first try by hitting enter on the password field
    try:
        password_input.send_keys(Keys.RETURN)
        # Wait briefly to see if the login proceeds
        time.sleep(short_load_wait)
        # Check if still on login page (Email field still present)
        if web_driver.find_elements(By.NAME, "Email"):
            # Fallback: click the login button directly
            login_btn = web_driver.find_element(By.ID, "loginBtn")
            login_btn.click()
    except Exception:   # noqa: BLE001
        # Fallback: click the login button directly
        try:
            login_btn = web_driver.find_element(By.ID, "loginBtn")
            login_btn.click()
        except Exception as e:  # noqa: BLE001
            logger.log_fatal_error(f"Login fails after trying Return and login button click: {e}", "debug")

    # Wait for successful login - we wait until "My Account" span appears
    try:
        WebDriverWait(web_driver, page_load_wait).until(
            expected_con.presence_of_element_located(
                (By.XPATH, "//span[text()='My Account']")
            ),
        )
    except TimeoutException:
        logger.log_fatal_error(
            f"Timeout after {page_load_wait} seconds occurred while waiting for the My Account element on the next page {login_url}."
        )
        return False

    except WebDriverException:
        logger.log_fatal_error(
            f"General web driver error while while waiting for the My Account element on the next page {login_url}."
        )
        return False

    # Login was successful
    return True


def get_watchlist_table(config, logger, web_driver) -> object:
    """Navigate to the specified watchlist URL.

    Args:
        config: The configuration manager instance.
        logger: The logger instance.
        web_driver: The Selenium WebDriver instance.

    Returns:
        object: a table object if successful, otherwise None.
    """
    watchlist_url = config.get("InvestSmart", "WatchlistURL")
    page_load_wait = config.get("InvestSmart", "LongPageLoad")

    try:
        web_driver.get(watchlist_url)

        # If redirected to fundlater, try again
        if web_driver.current_url.startswith("https://www.fundlater.com.au/"):
            web_driver.get(watchlist_url)

        # Wait for the watchlist table to load
        table_obj = WebDriverWait(web_driver, page_load_wait).until(
            expected_con.presence_of_element_located(
                (By.XPATH, "//table[@data-sortable-name='watchlist']")
            ),
        )

    except TimeoutException as e:
        logger.log_fatal_error(
            f"Timeout occurred while trying to load the watchlist page {watchlist_url}: {e}"
        )
        return None

    except WebDriverException as e:
        logger.log_fatal_error(
            f"General web driver error while trying to load the watchlist page {watchlist_url}: {e}"
        )
        return None

    time.sleep(1)  # Small delay to help page load properly
    return table_obj


def load_fund_code_cache() -> list:
    """Load the fund code cache as a list of dicts.

    Returns:
        list: A list of dictionaries containing fund names and their corresponding APIR codes.
    """
    if Path(FUND_CODE_CACHE_FILE).exists():
        with Path(FUND_CODE_CACHE_FILE).open("r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def save_fund_code_cache(cache):
    """Save the fund code cache as a list of dicts.

    Args:
        cache (list): A list of dictionaries containing fund names and their corresponding APIR codes.
    """
    with Path(FUND_CODE_CACHE_FILE).open("w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


def extract_apir_code(logger, driver, fund_name) -> str:
    """Extract the APIR code for a fund. First, check the cache. If not found, extract from the page and update the cache.

    Args:
        logger: The logger instance.
        driver: The Selenium WebDriver instance.
        fund_name: The name of the fund to extract the APIR code for.

    Returns:
        str: The APIR code if found, otherwise None.
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
        logger.log_message(f"Could not extract APIR code: {e}", "debug")

    # Save to cache if found
    if apir_code:
        cache.append({"fund_name": fund_name, "apir_code": apir_code})
        save_fund_code_cache(cache)
    return apir_code


def extract_fund_data(logger, table_obj) -> list:  # noqa: PLR0914
    """Extract fund data from the watchlist table, including APIR code from each fund's detail page, with caching.

    Args:
        logger: The logger instance.
        table_obj: The Selenium WebDriver element representing the watchlist table.

    Returns:
        list: A list of tuples containing fund data (APIR code, date, name, currency, price).
    """
    # Load the local timezone
    local_tz = datetime.now().astimezone().tzinfo
    try:
        headers = table_obj.find_elements(By.XPATH, ".//thead/tr/th")
    except InvalidSelectorException:
        logger.log_fatal_error(
            "InvalidSelectorException exception when scanning the watchlist table"
        )
        return None
    except WebDriverException:
        logger.log_fatal_error(
            "General web driver error when scanning the watchlist table"
        )
        return None

    if headers is None:
        logger.log_fatal_error("Could not find the watchlist table headers.")
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
        logger.log_fatal_error(
            "Could not find required columns in the watchlist table."
        )
        return None

    today_str = datetime.now(local_tz).strftime("%Y-%m-%d")
    fund_list = []
    rows = table_obj.find_elements(By.XPATH, ".//tbody/tr")
    if rows is None:
        logger.log_fatal_error(
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
            apir_code = extract_apir_code(logger, driver, fund_name)
            if not apir_code:
                driver.execute_script("window.open('');")
                driver.switch_to.window(driver.window_handles[1])
                driver.get(fund_url)
                WebDriverWait(driver, 10).until(
                    expected_con.presence_of_element_located((By.CSS_SELECTOR, "table.table-performance"))
                )
                apir_code = extract_apir_code(logger, driver, fund_name)
                driver.close()
                driver.switch_to.window(driver.window_handles[0])

            fund_list.append((apir_code, today_str, fund_name, "AUD", price_value))
        except WebDriverException as e:
            logger.log_fatal_error(f"Could not parse a row: {e}")

    return fund_list


def save_to_csv(config, data, file_path) -> bool:
    """Save the extracted fund data to a CSV file, including APIR code.

    Args:
        config: The configuration manager instance.
        data: A list of tuples containing fund data (APIR code, date, name, currency, price).
        file_path: The path to the CSV file where data will be saved.

    Returns:
        bool: True if the data was saved successfully, False otherwise.
    """
    # Today's date in dd/mm/yyyy format
    local_tz = datetime.now().astimezone().tzinfo
    today_str = datetime.now(local_tz).strftime("%d/%m/%Y")

    # Set the earliest date to be an offset from today using the DaysToSave setting
    days_to_save = config.get("Files", "DaysToSave") or 30
    earliest_date = datetime.now(local_tz).date() - timedelta(days=days_to_save)

    # ===== Handle existing CSV (read and remove today's rows) =====
    existing_rows = []
    header = ["Symbol", "Date", "Name", "Currency", "Price"]
    if file_path.exists():
        with file_path.open(newline="", encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile)
            header = next(reader, None)  # Read the header
            for row in reader:
                if row:
                    row_date = (
                        datetime.strptime(row[1], "%Y-%m-%d")
                        .astimezone(local_tz)
                        .date()
                    )
                    if row_date >= earliest_date and row[0] != today_str:
                        existing_rows.append(row)

    # ===== Write updated CSV =====
    with file_path.open("w", newline="", encoding="utf-8") as csvfile:
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


def main():
    # Get our default schema, validation schema, and placeholders
    schemas = ConfigSchema()

    # Initialize the SCConfigManager class
    try:
        config = SCConfigManager(
            config_file=CONFIG_FILE,
            default_config=schemas.default,  # Replace with your default config if needed
            validation_schema=schemas.validation,  # Replace with your validation schema if needed
            placeholders=schemas.placeholders  # Replace with your placeholders if needed
        )
    except RuntimeError as e:
        print(f"Configuration file error: {e}", file=sys.stderr)
        return

    # Initialize the SCLogger class
    try:
        logger = SCLogger(config.get_logger_settings())
    except RuntimeError as e:
        print(f"Logger initialisation error: {e}", file=sys.stderr)
        return

    # Setup email
    logger.register_email_settings(config.get_email_settings())

    # Setup the Chrome drive options
    driver = create_undetectable_chrome(config)

    try:
        if not try_login_bypass(config, logger, driver):
            # Cookies unavailable or invalid - we need to login to the website.

            # Delete any existing cookies file
            delete_cookies(config)

            if login(
                config,
                logger,
                driver,
                config.get("InvestSmart", "Username"),
                config.get("InvestSmart", "Password"),
            ):
                # Call this after a successful login
                save_cookies(config, logger, driver)
            else:
                driver.quit()
                sys.exit(1)

        # Navigate to the watchlist page
        table = get_watchlist_table(config, logger, driver)
        if table is None:
            driver.quit()
            sys.exit(1)

        fund_data = extract_fund_data(logger, table)
        if fund_data is None:
            driver.quit()
            sys.exit(1)

        csv_file_name = config.get("Files", "OutputCSV")
        csv_file_path = config.select_file_location(csv_file_name)
        if not save_to_csv(config, fund_data, csv_file_path):
            driver.quit()
            sys.exit(1)

    # Catch any unexpected exceptions
    except Exception as e:  # noqa: BLE001
        logger.log_fatal_error(
            f"An unexpected error occurred while writing: {e}"
        )
        driver.quit()
        sys.exit(1)

    logger.log_message(
        f"Data extracted and saved to {csv_file_name} successfully.", "summary"
    )

    driver.quit()

    # If the prior run fails, send email that this run worked OK
    if logger.get_fatal_error():
        logger.log_message(
            "Run was successful after a prior failure.", "summary"
        )
        logger.send_email(
            "Run recovery",
            "Portfolio Performance reporter run was successful after a prior failure.",
        )
        logger.clear_fatal_error()


if __name__ == "__main__":
    # Run the main module
    main()

    sys.exit(0)
# End of script
