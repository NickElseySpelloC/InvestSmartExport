"""Configuration schemas for use with the SCConfigManager class."""

class ConfigSchema:
    """Base class for configuration schemas."""

    def __init__(self):
        self.default = {
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
                "OutputCSV": "price_data.csv",
                "DaysToSave": 30,
                "LogfileName": "ISExportConfig.log",
                "LogfileMaxLines": 500,
                "LogfileVerbosity": "detailed",
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

        self.placeholders = {
            "InvestSmart": {
                "Username": "<Your InvestSmart Username>",
                "Password": "<Your InvestSmart Password>",
            },
            "Email": {
                "SendEmailsTo": "<Your email address here>",
                "SMTPUsername": "<Your SMTP username here>",
                "SMTPPassword": "<Your SMTP password here>",
            }
        }

        self.validation = {
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
                    "LogfileName": {"type": "string", "required": False, "nullable": True},
                    "LogfileMaxLines": {"type": "number", "min": 0, "max": 100000},
                    "LogfileVerbosity": {
                        "type": "string",
                        "required": True,
                        "allowed": ["none", "error", "warning", "summary", "detailed", "debug", "all"],
                    },
                    "ConsoleVerbosity": {
                        "type": "string",
                        "required": True,
                        "allowed": ["error", "warning", "summary", "detailed", "debug", "all"],
                    },
                 },
            },
            "Email": {
                "type": "dict",
                "schema": {
                    "EnableEmail": {"type": "boolean", "required": True},
                    "SendEmailsTo": {"type": "string", "required": False, "nullable": True},
                    "SMTPServer": {"type": "string", "required": False, "nullable": True},
                    "SMTPPort": {"type": "number", "required": False, "nullable": True, "min": 25, "max": 1000},
                    "SMTPUsername": {"type": "string", "required": False, "nullable": True},
                    "SMTPPassword": {"type": "string", "required": False, "nullable": True},
                    "SubjectPrefix": {"type": "string", "required": False, "nullable": True},
                },
            },
        }

