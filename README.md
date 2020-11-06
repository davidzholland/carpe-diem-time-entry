## Prerequisites

* Python 3 & Pip
   * Download and install from python.org
   * On Windows, ensure the install location (e.g. `;C:\Python37`) is added to your PATH environment variable. E.g. https://geek-university.com/python/add-python-to-the-windows-path/
* TKinter
   * Follow the instructions to install Tk at: https://tkdocs.com/tutorial/install.html
   * On OSX with pyenv you may need to reinstall python with tkinter environment vars as:
      * `brew install python --with-tcl-tk`
      * `PYTHON_CONFIGURE_OPTS="--with-tcltk-includes='-I/usr/local/opt/tcl-tk/include' --with-tcltk-libs='-L/usr/local/opt/tcl-tk/lib -ltcl8.6 -ltk8.6'" pyenv install 3.7.4`
* virtualenv
   * `pip install virtualenv`

## Setup

1. Clone the repository or download and extract the Zip archive

    ```bash
    git clone https://github.com/davidzholland/carpe-diem-time-entry
    ```

1. Use a virtual environment to isolate dependencies for this project from your local system.
   ```bash
   virtualenv venv
   source venv/bin/activate
   ```

1. Install the dependencies

    ```bash
    pip install -r requirements.txt
    ```

1. For Carpe Diem Desktop, get your Carpe Diem user details and secret

    Copy `.env.example` to `.env` (hint: `cp .env.example .env`). Replace the placeholders within `.env`, including the `<` `>` characters with the values derived from the steps below. Add your timekeeper Id as `timekeeperId` and your name to `name` as `JOHN.SMITH`. Ensure the last line is blank.
    
    To get the above values, proxy your phone through your computer.
    
    1. Install Carpe Diem Mobile on your phone and ensure you can login and submit entries. Typically available via your corporate intranet site or IT deparment.
    1. Connect your phone and computer to the same network
       * Note: Some corporate and public wifi networks block these requests, so using your own wifi network is preferred.
    1. On your phone change your network connect to [use a manual proxy](https://www.charlesproxy.com/documentation/faqs/using-charles-from-an-iphone/) to your computer's internal IP address
    1. On your phone trust the Charles SSL certificate ([instructions here](https://www.charlesproxy.com/documentation/using-charles/ssl-certificates))
    1. Install Charles Proxy on your computer
       * On the main page, click record
    1. With Charles recording, submit a time entry from Carpe Diem Mobile and watch for a request to `cdmobile/TimeKMSV.asp`.
    1. Note the domain in the request.
       * Setup SSL proxying: Proxy > SSL Proxying Settings > SSL Proxying > Add Location: <your-corporate-carpe-diem-domain>:443
    1. Submit another entry from your phone and find the entry in Charles to `cdmobile/TimeKMSV.asp` that contains `udid`, `key`, `id` and `dev` in the request content/headers. Copy these values into your `.env` file along with the full URL of the request to the `url` value in the `.env`.
    1. On your phone, remove the manual proxy from your network settings.
    1. On your phone, remove the trust setting for the Charles SSL certificate.

## Usage

1. Format your time entries into a CSV (save anywhere on your computer), and use the exact column headers specified below (in any order).
    
    **Required:**
    ``` 
    Date,Hours,Client,Matter Code,Jurisdiction,Task Code,Description
    ```

    **Optional:**
    * Matter Name
    * Max Entry Hours
       * concatenate entries for a single matter up to this limit.

1. If using Carpe Diem Web, get a temporary access token.
   1. Log into the CD Web site in your browser.
   2. Open your browser's developer tools/console and copy `authorizationData_CarpeWeb` from the session storage.

1. From a terminal, enter the command below and follow the instructions/prompts.
    
    ``` 
    python import.py
    ```

1. Log into Carpe Diem and close the entries.
