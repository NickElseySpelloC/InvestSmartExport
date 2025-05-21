"""General utility functions for the project."""

import inspect
import smtplib
import sys
import traceback
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import yaml
from cerberus import Validator

CONFIG_FILE = "ISExportConfig.yaml"
FATAL_ERROR_FILE = "FatalErrorTracking.txt"


def merge_configs(default, custom):
    """Merges two dictionaries recursively, with the custom dictionary."""
    for key, value in custom.items():
        if isinstance(value, dict) and key in default:
            merge_configs(default[key], value)
        else:
            default[key] = value
    return default


class ConfigManager:
    """Class to manage system configuration and file paths."""

    def __init__(self):
        self.config_file_path = self.select_file_location(CONFIG_FILE)
        self.default_config = {
            "InvestSmart": {
                "HeadlessMode": False,
                "LoginURL": "https://www.investsmart.com.au/identity/logon",
                "LongPageLoad": 30,
                "ShortPageLoad": 10,
                "Username": None,
                "Password": None,
                "WatchlistURL": "https://www.investsmart.com.au/portfolio-manager/watchlist/funds/850523?PortfolioID=184911",
            },
            "Files": {
                "OutputCSV": "fund_data.csv",
                "DaysToSave": 30,
                "MonitoringLogFile": "PowerControllerUI.log",
                "MonitoringLogFileMaxLines": 500,
                "LogFileVerbosity": "summary",
                "ConsoleVerbosity": "summary",
            },
            "Email": {
                "EnableEmail": False,
                "SendEmailsTo": None,
                "SMTPServer": None,
                "SMTPPort": None,
                "SMTPUsername": None,
                "SMTPPassword": None,
                "SubjectPrefix": None,
            },
        }

        self.default_config_schema = {
            "InvestSmart": {
                "type": "dict",
                "schema": {
                    "HeadlessMode": {
                        "type": "boolean",
                        "required": False,
                        "nullable": True,
                    },
                    "LoginURL": {"type": "string", "required": True},
                    "LongPageLoad": {"type": "number", "required": True},
                    "ShortPageLoad": {"type": "number", "required": True},
                    "Username": {"type": "string", "required": True},
                    "Password": {"type": "string", "required": True},
                    "WatchlistURL": {"type": "string", "required": True},
                },
            },
            "Files": {
                "type": "dict",
                "schema": {
                    "OutputCSV": {"type": "string", "required": True},
                    "DaysToSave": {
                        "type": "number",
                        "required": False,
                        "nullable": True,
                        "min": 0,
                        "max": 365,
                    },
                    "MonitoringLogFile": {
                        "type": "string",
                        "required": False,
                        "nullable": True,
                    },
                    "MonitoringLogFileMaxLines": {
                        "type": "number",
                        "min": 0,
                        "max": 100000,
                    },
                    "LogFileVerbosity": {
                        "type": "string",
                        "required": True,
                        "allowed": [
                            "none",
                            "error",
                            "warning",
                            "summary",
                            "detailed",
                            "debug",
                            "all",
                        ],
                    },
                    "ConsoleVerbosity": {
                        "type": "string",
                        "required": True,
                        "allowed": [
                            "error",
                            "warning",
                            "summary",
                            "detailed",
                            "debug",
                            "all",
                        ],
                    },
                },
            },
            "Email": {
                "type": "dict",
                "schema": {
                    "EnableEmail": {"type": "boolean", "required": True},
                    "SendEmailsTo": {
                        "type": "string",
                        "required": False,
                        "nullable": True,
                    },
                    "SMTPServer": {
                        "type": "string",
                        "required": False,
                        "nullable": True,
                    },
                    "SMTPPort": {
                        "type": "number",
                        "required": False,
                        "nullable": True,
                        "min": 25,
                        "max": 1000,
                    },
                    "SMTPUsername": {
                        "type": "string",
                        "required": False,
                        "nullable": True,
                    },
                    "SMTPPassword": {
                        "type": "string",
                        "required": False,
                        "nullable": True,
                    },
                    "SubjectPrefix": {
                        "type": "string",
                        "required": False,
                        "nullable": True,
                    },
                },
            },
        }

        self.load_config()

    def load_config(self):
        """Load the configuration file. If it does not exist, create it with default values."""
        if not Path(self.config_file_path).exists():
            with Path(self.config_file_path).open("w", encoding="utf-8") as file:
                yaml.dump(self.default_config, file)

        with Path(self.config_file_path).open(encoding="utf-8") as file:
            v = Validator()
            config_doc = yaml.safe_load(file)

            self.validate_no_placeholders(config_doc)

            if not v.validate(config_doc, self.default_config_schema):
                print(f"Error in configuration file: {v.errors}", file=sys.stderr)
                sys.exit(1)

        self.active_config = merge_configs(self.default_config, config_doc)

    def validate_no_placeholders(self, config_section, path=""):
        # Define expected placeholders
        placeholders = {
            "<Your InvestSmart Username>",
            "<Your InvestSmart Password>",
            "<Your email address here>",
            "<Your SMTP server here>",
            "<Your SMTP username here>",
            "<Your SMTP password here>",
        }

        if isinstance(config_section, dict):
            for key, value in config_section.items():
                self.validate_no_placeholders(value, f"{path}.{key}" if path else key)
        elif isinstance(config_section, list):
            for idx, item in enumerate(config_section):
                self.validate_no_placeholders(item, f"{path}[{idx}]")
        elif str(config_section).strip() in placeholders:
            print(
                f"ERROR: Config value at '{path}' is still set to placeholder: '{config_section}'",
                file=sys.stderr,
            )
            print(
                f"Please update {CONFIG_FILE} with your actual credentials.",
                file=sys.stderr,
            )
            sys.exit(1)

    def select_file_location(self, file_name: str) -> str:
        """
        Selects the file location for the given file name.

        :param file_name: The name of the file to locate.
        :return: The full path to the file. If the file does not exist in the current directory, it will look in the script directory.
        """
        current_dir = Path.cwd()
        script_dir = Path(__file__).resolve().parent
        file_path = current_dir / file_name
        if not file_path.exists():
            file_path = script_dir / file_name
        return str(file_path)


class UtilityFunctions:
    """General utility functions."""

    def __init__(self, config_manager_object):
        self.config_manager = config_manager_object
        self.config = self.config_manager.active_config
        self.cookie_file = self.config_manager.select_file_location("cookies.json")
        self.trim_log_file()

    def trim_log_file(self):
        """Trims the log file to a maximum number of lines."""
        # Truncate the log file if it exists
        if self.config["Files"]["MonitoringLogFile"] is not None:
            file_path = self.config_manager.select_file_location(
                self.config["Files"]["MonitoringLogFile"]
            )

            if Path(file_path).exists():
                # Monitoring log file exists - truncate excess lines if needed.
                with Path(file_path).open(encoding="utf-8") as file:
                    max_lines = self.config["Files"]["MonitoringLogFileMaxLines"]

                    if max_lines > 0:
                        lines = file.readlines()

                        if len(lines) > max_lines:
                            # Keep the last max_lines rows
                            keep_lines = (
                                lines[-max_lines:] if len(lines) > max_lines else lines
                            )

                            # Overwrite the file with only the last 1000 lines
                            with Path(file_path).open("w", encoding="utf-8") as file2:
                                file2.writelines(keep_lines)

                            self.log_message(
                                "Housekeeping of log file completed.", "debug"
                            )

    def log_message(self, message: str, verbosity: str):
        """Writes a log message to the console and/or a file based on verbosity settings."""
        local_tz = datetime.now().astimezone().tzinfo
        config_file_setting_str = self.config["Files"]["LogFileVerbosity"]
        console_setting_str = self.config["Files"]["ConsoleVerbosity"]

        if verbosity not in ["error", "warning", "summary", "detailed", "debug", "all"]:
            print(
                "Invalid verbosity setting passed to write_log_message().",
                file=sys.stderr,
            )
            sys.exit(1)

        switcher = {
            "none": 0,
            "error": 1,
            "warning": 2,
            "summary": 3,
            "detailed": 4,
            "debug": 5,
            "all": 6,
        }

        config_file_setting = switcher.get(config_file_setting_str, 0)
        console_setting = switcher.get(console_setting_str, 0)
        message_level = switcher.get(verbosity, 0)

        # Deal with console message first
        if console_setting >= message_level and console_setting > 0:
            if verbosity == "error":
                print("ERROR: " + message, file=sys.stderr)
            elif verbosity == "warning":
                print("WARNING: " + message)
            else:
                print(message)

        # Now write to the log file if needed
        if self.config["Files"]["MonitoringLogFile"] is not None:
            file_path = self.config_manager.select_file_location(
                self.config["Files"]["MonitoringLogFile"]
            )
            error_str = (
                " ERROR"
                if verbosity == "error"
                else " WARNING"
                if verbosity == "warning"
                else ""
            )
            if config_file_setting >= message_level and config_file_setting > 0:
                with Path(file_path).open("a", encoding="utf-8") as file:
                    if message == "":
                        file.write("\n")
                    else:
                        file.write(
                            f"{datetime.now(local_tz).strftime('%Y-%m-%d %H:%M:%S')}{error_str}: {message}\n"
                        )

    def report_fatal_error(self, message, report_stack=False, exit_program=False):  # noqa: FBT002
        """Report a fatal error and exit the program."""
        function_name = None
        stack = inspect.stack()
        # Get the frame of the calling function
        calling_frame = stack[1]
        # Get the function name
        function_name = calling_frame.function
        if function_name == "<module>":
            function_name = "main"
        # Get the class name (if it exists)
        class_name = None
        if "self" in calling_frame.frame.f_locals:
            class_name = calling_frame.frame.f_locals["self"].__class__.__name__
            full_reference = f"{class_name}.{function_name}()"
        else:
            full_reference = function_name + "()"

        stack_trace = traceback.format_exc()
        if report_stack:
            message += f"\n\nStack trace:\n{stack_trace}"

        self.log_message(f"Function {full_reference}: FATAL ERROR: {message}", "error")

        # Try to send an email
        if function_name != "send_email" and not self.fatal_error_tracking("get"):
            self.send_email(
                "InvestSmart Export terminated with a fatal error",
                f"{message} \nAdditional emails will not be sent for concurrent errors - check the log file for more information. An email when be sent when the system recovers.",
            )

        # record the error in in a file so that we keep track of this next time round
        self.fatal_error_tracking("set", message)

        # Exit the program
        if exit_program:
            sys.exit(1)

    def fatal_error_tracking(self, mode, message=None):
        """
        Keep track of fatal errors by writing the last one to a file Used to keep track of concurrent fatal errors.

        :param mode:
            "get": Returns True if the file exists, False otherwise
            "set": Writes the message to the file. If message is None, deletes the file.
        :param message: The message to write to the file. Only used in "set" mode.
        """
        file_path = self.config_manager.select_file_location(FATAL_ERROR_FILE)

        if mode == "get":
            # Check if the file exists
            return Path(file_path).exists()
        if mode == "set":
            # If message is None, delete the file
            if message is None:
                if Path(file_path).exists():
                    Path(file_path).unlink()
                    return True
                return False
            # Write the message to the file
            with Path(file_path).open("w", encoding="utf-8") as file:
                file.write(message)
        return True

    def send_email(self, subject, body):
        """Sends an email using Gmail SMTP server."""
        # Make sure we have a full configuration for email sending
        if (
            self.config["Email"]["EnableEmail"] is None
            or not self.config["Email"]["EnableEmail"]
        ):
            self.log_message(
                f"SMTP settings not fully configured for sending emails. Skipping sending the email {subject}.",
                "debug",
            )
            return

        # Load the Gmail SMTP server configuration
        send_to = self.config["Email"]["SendEmailsTo"]
        smtp_server = self.config["Email"]["SMTPServer"]
        smtp_port = self.config["Email"]["SMTPPort"]
        sender_email = self.config["Email"]["SMTPUsername"]
        app_password = self.config["Email"]["SMTPPassword"]

        if any(
            not var
            for var in [send_to, smtp_server, smtp_port, sender_email, app_password]
        ):
            self.report_fatal_error(
                "SMTP configuration is incomplete. Please check the settings.",
                exit_program=True,
            )

        try:
            # Create the email
            msg = MIMEMultipart()
            msg["From"] = sender_email
            msg["To"] = send_to
            if self.config["Email"]["SubjectPrefix"] is not None:
                msg["Subject"] = self.config["Email"]["SubjectPrefix"] + subject
            else:
                msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            # Connect to the Gmail SMTP server
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()  # Upgrade the connection to secure
                server.login(sender_email, app_password)  # Log in using App Password
                server.sendmail(
                    sender_email, send_to, msg.as_string()
                )  # Send the email

        except RuntimeError as e:
            self.report_fatal_error(
                f"Failed to send email with subject {msg['Subject']}: {e}",
                exit_program=True,
            )

    def __getitem__(self, key):
        """Allows access to the state dictionary using square brackets."""
        return self[key]

    def __setitem__(self, index, value):
        """Allows setting values in the state dictionary using square brackets."""
        self[index] = value
