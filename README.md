# InvestSmart Download
This app is designed to login to the [InvestSmart website](https://www.investsmart.com.au/), navigate to a predefined watchlist page and download the fund prices. It's a companion project to the [YahooFinance app](https://github.com/NickElseySpelloC/YahooFinance) and is used to download Aussie wholesale fund prices not available from Yahoo. This app uses Selenium to "scrape" the InvestSmart web page, so it might not be 100% reliable. 

**Note**: This app can't deal with 2FA authentication on the InvestSmart website. You need to have this disable for this app to work correctly. 

# Features
* Automatically login to InvestSmart
* Saves the InvestSmart cookies for a faster login the next time
* Error and retry handling
* Designed to be run as a scheduled task (e.g. from crontab)
* Can send email notifications when there is a critical failure.

# Installation & Setup
## Prerequisites
* Python 3.x installed:
macOS: `brew install python3`
Windows: `winget install python3 --source winget --scope machine`
* UV for Python installed:
macOS: 'brew install uvicorn'
Windows: `pip install uv`

The shell script used to run the app (_launch.sh_ or _launch.ps1_) is uses the *uv sync* command to ensure that all the prerequitie Python packages are installed in the virtual environment.

# Configuration File 
The script uses the *config.yaml* YAML file for configuration. An example of included with the project (*config.yaml.example*). Copy this to *config.yaml* before running the app for the first time.  Here's an example config file:
```
InvestSmart:
    HeadlessMode: False
    LoginURL: https://www.investsmart.com.au/identity/logon
    ShortPageLoad: 10
    LongPageLoad: 20
    Username: john.doe@gmail.com
    Password: <Your InvestSmart password>
    WatchlistURL: https://www.investsmart.com.au/portfolio-manager/watchlist/funds/12345?PortfolioID=67890

Files:
    OutputCSV: price_data.csv
    DaysToSave: 90
    Logfile: logfile.log
    LogfileMaxLines: 200
    LogfileVerbosity: detailed
    ConsoleVerbosity: detailed

Email:
    EnableEmail: True
    SendEmailsTo: john.doe@gmail.com
    SMTPServer: smtp.gmail.com
    SMTPPort: 587
    SMTPUsername: john.doe@gmail.com
    SMTPPassword: <Your SMTP password>
    SubjectPrefix: "[Yahoo Finance Downloader] "
```

## Configuration Parameters
### Section: InvestSmart

| Parameter | Description | 
|:--|:--|
| HeadlessMode | If False, the browser window won't be displayed when scraping the InvestSmart watchlist. You should set this to True initially to make sure everything is working OK. |
| LoginURL | The URL for the InvestSmart login page. Defaults to https://www.investsmart.com.au/identity/logon |
| ShortPageLoad | The timeout when waiting for a web page to load after the login has been completed. |
| LongPageLoad | The timeout when waiting for the login to completed. |
| Username | Your InvestSmart account username |
| Password | Your InvestSmart account password |
| WatchlistURL | The complete URL to the fund watchlist page that you want to download. |

### Section: Files

| Parameter | Description | 
|:--|:--|
| OutputCSV | The name of the CSV file to write prices to. If the file already exists, prices will be appended to the end of the CSV file. | 
| DaysToSave | Fund price data is appended to the CSV file. This setting sets the maximum number of days to keep price data for. Set to 0 or blank if not truncation is required. | 
| LogfileName | The name of the log file, can be a relative or absolute path. | 
| LogfileMaxLines | Maximum number of lines to keep in the log file. If zero, file will never be truncated. | 
| LogfileVerbosity | The level of detail captured in the log file. One of: none; error; warning; summary; detailed; debug; all | 
| ConsoleVerbosity | Controls the amount of information written to the console. One of: error; warning; summary; detailed; debug; all. Errors are written to stderr all other messages are written to stdout | 

### Section: Email

| Parameter | Description | 
|:--|:--|
| EnableEmail | Set to *True* if you want to allow the app to send emails. If True, the remaining settings in this section must be configured correctly. | 
| SMTPServer | The SMTP host name that supports TLS encryption. If using a Google account, set to smtp.gmail.com |
| SMTPPort | The port number to use to connect to the SMTP server. If using a Google account, set to 587 |
| SMTPUsername | Your username used to login to the SMTP server. If using a Google account, set to your Google email address. |
| SMTPPassword | The password used to login to the SMTP server. If using a Google account, create an app password for the app at https://myaccount.google.com/apppasswords  |
| SubjectPrefix | Optional. If set, the app will add this text to the start of any email subject line for emails it sends. |

# Running the Script
Run the app using the relavant shell script for your operating system:

## macOS / Linux
`launch.sh`

## Windows 
`powershell -ExecutionPolicy ByPass -c  .\launch.ps1`

# Troubleshooting
## "No module named xxx"
Ensure all the Python modules are installed in the virtual environment. Make sure you are running the app via the *launch* script.

## ModuleNotFoundError: No module named 'requests' (macOS)
If you can run the script just fine from the command line, but you're getting this error when running from crontab, make sure the crontab environment has the Python3 folder in it's path. First, at the command line find out where python3 is being run from:

`which python3`

And then add this to a PATH command in your crontab:

`PATH=/usr/local/bin:/usr/bin:/bin`
`0 8 * * * /Users/bob/scripts/InvestSmartExport/launch.sh`