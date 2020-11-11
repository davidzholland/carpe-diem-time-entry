import os
from dotenv import load_dotenv
import tkinter as tk
from tkinter import filedialog
import csv
import json
import urllib
import uuid
import time
import datetime
from urllib.parse import urlparse
from dateutil import parser
import requests
import math
from decimal import Decimal
import hmac
import jwt
import timeago
import calendar
import readline


REQUIRED_HOURS_PER_WEEKDAY = 8
STATUS_TRANSFERRED = '4'
# Load the .env configuration
load_dotenv()

app_configs = {
    'cd_web': {
        'endpoints': {
            'submit': 'https://tik-prd-usc-cd-cdweb-apiapp.azurewebsites.net/api/TimeEntry/AddTimeEntry',
            'view-month': 'https://tik-prd-usc-cd-cdweb-apiapp.azurewebsites.net/api/MonthView/Month/{0}/Tkpr/{1}'
        }
    },
    'cd_desktop': {
        'endpoints': {
            'submit': 'https://cdmobile.fticonsulting.com/cdmobile/TimeKMSV.asp'
        }
    }
}
selected_app = None
access_token = None
from_date = ""
to_date = ""
submission_delay = .1
print_styles = {
    'WARNING': '\033[91m',
    'ENDC': '\033[0m'
}
default_max_hours_per_entry = 4

def import_time():
    warn('WARNING: USE AT YOUR OWN RISK. BY PROCEEDING YOU ACKNOWLEDGE THIS SOFTWARE IS EXPERIMENTAL AND FOR TESTING ONLY')
    set_app()
    analyze_existing_entries()
    set_date_range()
    submit_time_entries()

def analyze_existing_entries():
    global from_date
    # Analyze prior month
    last_month_date = get_last_day_of_prior_month()
    analyze_month_entries(last_month_date)
    # Analyze current month
    today = datetime.date.today()
    missing_entry_dates = analyze_month_entries(today)
    # Set default submission start date to earliest current month date with missing entries
    if len(missing_entry_dates) > 0:
        from_date = min(missing_entry_dates)

def analyze_month_entries(end_date):
    missing_entry_dates = []
    start_date = end_date.replace(day = 1)
    weekdays = get_weekdays(start_date, end_date)
    totals = get_month_totals(start_date)
    transferred_totals = [i for i in totals if i['status'] == STATUS_TRANSFERRED]
    for weekday in weekdays:
        day_entries = [i for i in transferred_totals if i['dateWorked'] == weekday.strftime('%Y-%m-%dT00:00:00')]
        day_total_seconds = sum(i['dateTotal'] for i in day_entries)
        day_total_hours = (day_total_seconds / 60) / 60
        if day_total_hours < REQUIRED_HOURS_PER_WEEKDAY:
            missing_entry_dates.append(weekday)
    if len(missing_entry_dates) > 0:
        formatted_missing_entry_dates = [i.strftime('%Y-%m-%d') for i in missing_entry_dates]
        warn('WARNING: ' + end_date.strftime('%B') + ' is missing hours for: ' + str(formatted_missing_entry_dates))
    else:
        success(end_date.strftime('%B') + ' looks good!')
    return missing_entry_dates

def get_month_totals(date):
    url = app_configs[selected_app]['endpoints']['view-month'].format(date.strftime('%Y-%m-%d') + 'T00:00:00.000', os.getenv('timekeeperId'))
    headers = get_view_headers(url)
    try:
        result = requests.get(url, headers=headers)
        if result.status_code == 200:
            return result.json()
        else:
            print('There was a problem fetching: ', result.status_code, result.text)
    except requests.exceptions.RequestException as e:
        print('Fetching failed with error code - %s.' % e.code)
        error_message = e.read()
        print(error_message)
        return False

def get_weekdays(start, end, excluded=(6, 7)):
    days = []
    first_day = start
    while first_day <= end:
        if first_day.isoweekday() not in excluded:
            days.append(first_day)
        first_day += datetime.timedelta(days=1)
    return days

def get_last_day_of_prior_month():
    today = datetime.date.today()
    first = today.replace(day=1)
    return first - datetime.timedelta(days=1)

def get_month_day_range(date):
    """
    For a date 'date' returns the start and end date for the month of 'date'.

    Month with 31 days:
    >>> date = datetime.date(2011, 7, 27)
    >>> get_month_day_range(date)
    (datetime.date(2011, 7, 1), datetime.date(2011, 7, 31))

    Month with 28 days:
    >>> date = datetime.date(2011, 2, 15)
    >>> get_month_day_range(date)
    (datetime.date(2011, 2, 1), datetime.date(2011, 2, 28))
    """
    first_day = date.replace(day = 1)
    last_day = date.replace(day = calendar.monthrange(date.year, date.month)[1])
    return first_day, last_day

def set_app():
    global selected_app
    global access_token
    # Hard-code selection for now
    selected_app = 'cd_web'
    if selected_app == 'cd_web':
        print('Copy your access token from your browser\'s session parameter "authorizationData_CarpeWeb".')
        access_token = input('Access token: ').replace('"', '')
        if is_access_token_valid() == False:
            print('Please update the access token in the .env file and try again.')
            exit()

def set_date_range():
    global from_date
    global to_date

    print('Please specify the date range to import (From/To).')
    from_date = get_from_date()
    to_date = get_to_date()
    if False == confirm("Please confirm the date range: " + human_date(from_date) + " - " + human_date(to_date)):
        exit()

def get_from_date():
    global from_date
    today = datetime.date.today()
    if today.weekday() == 0:
        last_monday = today - datetime.timedelta(days=7)
    else:
        last_monday = today - datetime.timedelta(days=today.weekday())
    example_date_input = human_date(from_date) if from_date else human_date(last_monday)
    user_date = input('From date: (i.e. ' + example_date_input + '): ')
    if "" == user_date:
        user_date = example_date_input
    return parser.parse(user_date)

def get_to_date():
    today = datetime.date.today()
    example_date_input = human_date(today)
    user_date = input('To date: (i.e. ' + example_date_input + '): ')
    if "" == user_date:
        user_date = example_date_input
    return parser.parse(user_date)

def human_date(date):
    return date.strftime('%a, %b') + ' ' + date.strftime('%d').lstrip('0')

def prepare_entries_queue():
    entries_queue = []
    print('Opening dialog where you can choose the CSV to import...')
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(defaultextension=".csv", filetypes=(("CSV file", "*.csv"),("All Files", "*.*") ))
    with open( file_path, "r" ) as theFile:
        reader = csv.DictReader( theFile )
        for entry in reader:
            if 'Date' in entry and '' != entry['Date']:
                entry_date = parser.parse(entry['Date'])
                if (entry_date >= from_date and entry_date <= to_date):
                    entries_queue.append(entry)
    if len(entries_queue) <= 0:
        print("No entries found for " + str(from_date))
        exit()
    #print("Preview: ")
    #for entry in entries_queue:
    #    print(entry)
    display_queue_summary(entries_queue)
    entries_queue = combine_daily_matter_entries(entries_queue)
    return entries_queue

def submit_time_entries():
    entries_queue = prepare_entries_queue()
    print("Entries to submit: " + str(len(entries_queue)))
    error_count = 0
    if confirm("Would you like to proceed?"):
        print("Submitting...")
        for entry in entries_queue:
            if False == submit_time_entry(entry):
                error_count += 1
            time.sleep(submission_delay)
        if error_count > 0:
            warn("There was an issue submitting the time entries. Please review any errors above and correct any issues in Carpe Diem.")
        else:
            "Your time has been staged"
            warn("ACTION REQUIRED: Time entries are staged, but not yet closed. Please close your time via Carpe Diem")

def display_queue_summary(entries_queue):
    total_hours = get_total_hours(entries_queue)
    matter_column = 'Matter Name' if 'Matter Name' in entries_queue[0] else 'Matter Code'
    hours_by_matter = get_hours_by_key(entries_queue, matter_column)
    hours_by_date = get_hours_by_key(entries_queue, 'Date')
    print('By Matter:')
    print_hours_table(hours_by_matter, 'hours')
    print('By Date:')
    print_hours_table(hours_by_date, 'label', 30, 8)

def combine_daily_matter_entries(entries_queue):
    response = []
    combined_entries = {}
    hours_by_matter = get_hours_by_key(entries_queue, 'Matter Code')
    running_hours_by_matter = {}
    combined_group_number = 1
    for entry in entries_queue:
        matter_code = entry['Matter Code']
        if (matter_code not in running_hours_by_matter):
            running_hours_by_matter[matter_code] = 0
        running_hours_by_matter[matter_code] = running_hours_by_matter[matter_code] + Decimal(entry['Hours'])
        matter_hours = hours_by_matter[matter_code]
        max_hours_per_entry = default_max_hours_per_entry
        if ('Max Entry Hours' in entry and '' != entry['Max Entry Hours']):
            max_hours_per_entry = Decimal(entry['Max Entry Hours'])
        # Generate combined key
        combined_key = format_combined_key(entry['Date'], matter_code, combined_group_number)
        if (combined_key in combined_entries):
            new_combined_hours = Decimal(combined_entries[combined_key]['Hours']) + Decimal(entry['Hours'])
            if (new_combined_hours > max_hours_per_entry):
                combined_group_number += 1
                combined_key = format_combined_key(entry['Date'], matter_code, combined_group_number)
        # Check if the entry should be added to a new group or existing group
        if combined_key not in combined_entries:
            # New group of entries for this matter
            combined_entries[combined_key] = entry
        else:
            # Concatenate to existing group for this date and matter
            combined_entries[combined_key]['Hours'] = Decimal(combined_entries[combined_key]['Hours']) + Decimal(entry['Hours'])
            # Concatenate descriptions for the same date & matter
            # Don't concatenate duplicate entry descriptions
            if entry['Description'] not in combined_entries[combined_key]['Description']:
                combined_entries[combined_key]['Description'] += '; ' + entry['Description']
    # Format into a list
    for key, value in combined_entries.items():
        response.append(value)
    return response

def format_combined_key(date, matter_code, group_number):
    return format_date(date, "%Y%m%d") + '-' + matter_code + '-' + str(group_number)

def print_hours_table(hours_dict, sort_type = 'hours', width = 75, lt_threshold = False):
    total_hours = 0
    print('|'.ljust(width, '-'))
    print(('| Hours   Description').ljust(75))
    print('|'.ljust(width, '-'))
    iterator = sorted(hours_dict)
    if 'hours' == sort_type:
        iterator = sorted(hours_dict, key=hours_dict.get, reverse=True)
    for description in iterator:
        if False != lt_threshold and hours_dict[description] < lt_threshold:
            print_style = print_styles['WARNING']
        else:
            print_style = ""
        hours_formatted = str(hours_dict[description]).zfill(5)
        print(("| " + print_style + hours_formatted + " - " + description).ljust(width) + print_styles['ENDC'])
        total_hours += Decimal(hours_dict[description])
    print('|'.ljust(width, '-'))
    print("| " + (str(total_hours).zfill(5)) + " - Total hours")
    print('|'.ljust(width, '-'))
    print('')

def get_hours_by_key(entries_queue, key_name = 'Matter Code'):
    hours_by_key = {}
    for entry in entries_queue:
        key_value = entry[key_name]
        if key_value not in hours_by_key:
            hours_by_key[key_value] = 0
        hours_by_key[key_value] += Decimal(entry['Hours'])
    return hours_by_key

def get_total_hours(entries_queue):
    hours = 0
    for entry in entries_queue:
        hours += Decimal(entry['Hours'])
    return hours

def confirm(question):
    response = input(question + " [y/n] ")
    return response.lower() in ["y", ""]

def submit_time_entry(entry):
    url = app_configs[selected_app]['endpoints']['submit']
    data = prepare_data(entry)
    headers = get_submit_headers(data, url)
    # submit request
    try:
        result = requests.post(url, data=data, headers=headers)
        if result.status_code == 200:
            print('Success staging entry: ', result.json()['timeID'])
        else:
            print('There was a problem submitting the entry: ', result.status_code, result.text)
    except requests.exceptions.RequestException as e:
        print('Submission failed with error code - %s.' % e.code)
        error_message = e.read()
        print(error_message)
        return False

def get_submit_headers(data, url):
    headers = get_common_headers(url)
    if selected_app == 'cd_web':
        headers['Delta'] = generate_delta(data)
        headers['content-type'] = 'application/json'
    return headers

def get_view_headers(url):
    headers = get_common_headers(url)
    if selected_app == 'cd_web':
        headers['Cache-Control'] = 'application/json'
    return headers

def get_common_headers(url):
    parsed_url = urlparse(url)
    if selected_app == 'cd_desktop':
        return {
            'Host': parsed_url.hostname,
            'Accept': '*/*',
            'Accept-Language': 'en-us',
            'User-Agent': 'Carpe%20Diem/201401316 CFNetwork/887 Darwin/17.0.0'
        }
    else:
        return {
            "accept": "application/json",
            "Referer": "https://us.carpe.tikit.com/",
            "Authorization": "Bearer " + access_token,
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.183 Safari/537.36",
        }

def is_access_token_valid():
    try:
        decoded_token = jwt.decode(access_token, verify=False)
    except Exception as e:
        warn('Unable to decode token: ' + str(e), severity=2)
        print('Please double check the token and try again.')
        exit()
    time_diff = decoded_token['exp'] - time.time()
    dt_object = datetime.datetime.fromtimestamp(decoded_token['exp'])
    verb = 'expires' if time_diff > 0 else 'expired'
    print('Access token ' + verb + ' ' + timeago.format(dt_object))
    return time_diff > 10 # We need at least 10 seconds left to proceed

def generate_delta(data):
    decoded_token = jwt.decode(access_token, verify=False)
    secret_passphrase = str(decoded_token['nbf']) + decoded_token['unique_name'] + "CarpeDiem"
    return hmac.new(secret_passphrase.encode('utf-8'), data.encode('utf-8'), 'MD5').hexdigest()

def prepare_data(entry):
    data = {}
    current_datetime = datetime.datetime.now()
    hours = format_hours( entry['Hours'] )
    client = entry['Matter Code'].split('.')[0]
    matter = format_matter( entry['Matter Code'] )
    info = format_info(entry)
    date = format_date(entry['Date'])
    if selected_app == 'cd_desktop':
        data = {
            'svc': 'add',
            'info': info,
            'hour': str(hours),
            'id': os.getenv('id'),
            'tbcl': 'N',
            'udid': os.getenv('udid'),
            'date': date,
            'key': os.getenv('key'),
            'guid': str(uuid.uuid4()).upper(),
            'desc': entry['Description'],
            'dev': os.getenv('dev')
        }
    else:
        # TODO: Test further to ensure below format is correct
        data = {
            "timeEntry": {
                "clientId": client,
                "clientName": "FTI/Forensics and Litigation Consulting (NON BIL",  # TODO: Automate
                "projectId": matter,
                "projectName": "NB:  FEDA Dev Group - General PD", # TODO: Automate
                "timekeeperId": os.getenv('timekeeperId'),
                "timekeeperName": os.getenv('timekeeperName'),
                "dateWorked": parser.parse(date).strftime("%Y-%m-%d") + "T00:00:00.000",
                "narrativeForSheetview": entry['Description'],
                "billable": "NB",
                "billableOverriden": "0",
                "tempWorklistId": "",
                "rawTime": hours * 60 * 60, # Seconds
                "roundTime": round(hours * 60 * 60), # Seconds
                "otherTime": 0,
                "remainingRawTime": 0,
                "remainingRoundTime": 0,
                "roundTimeDisplayValue": str('%.2f' % hours),
                "rawTimeDisplayValue": str_timedelta(datetime.timedelta(hours=hours)),
                "spellChecked": 0,
                "timeId": "",
                "status": "0",
                "nickname": "",
                "source": "E",
                "comments": "",
                "startStopSequences": [],
                "offset": -6,
                "worklistId": "",
                "userCreated": os.getenv('name'),
                "userEdited": os.getenv('name'),
                "dateCreated": current_datetime.isoformat(),
                "dateEdited": current_datetime.isoformat(),
                "dateLastModified": current_datetime.isoformat(),
                "isTimerRunning": False,
                "userAddedFields": {},
                "roundingValue": 6,
                "userCodes": {
                    "Code1": entry['Task Code'], # Optional
                    "Code4": entry['Jurisdiction']
                },
                "userCodeIdDesc": {
                    "Code4": "NY-NYC:New York, New York City"
                },
                "isAddEntry": True,
                # "spellCheckRequired": True
            },
            "saveEntrySteps": [
                0,
                2,
                3,
                5,
                7
            ],
            "worklistSuggestionCount": -1,
            "spellCheckConfig": {
                "ignoreAllCaps": False,
                "ignoreCappedWords": False,
                "ignoreDomainName": False,
                "ignoreDoubleWord": False,
                "ignoreMixedCase": False,
                "ignoreMixedDigits": False,
                "spellCheckAddEdit": False
            },
            "defaultLangForSpellCheck": "en-US"
        }
        data = json.dumps(data, separators=(',', ':'))  # Separators are important in generating Delta
    return data

def str_timedelta(td):
    """Convert a timedelta to a string"""
    s = str(td).split(", ", 1)
    a = s[-1]
    if a[1] == ':':
        a = "0" + a
    s2 = s[:-1] + [a]
    return ", ".join(s2)

def format_hours(hours):
    return math.ceil(float(hours) * 10) / 10

def format_info(entry):
    client = format_client( entry['Client'] )
    matter = format_matter( entry['Matter Code'] )
    info = "|Client=" + client
    info += ";" + "Matter=" + matter
    info += ";" + "Jurisdiction=" + entry['Jurisdiction']
    info += ";" + "Task Code=" + entry['Task Code']
    return info

def format_client(client):
    return client.zfill(6) if "" != client else ""

def format_matter(matter):
    return format(float(matter), '.4f').zfill(11)

def format_date(date, format = "%Y/%m/%d"):
    return parser.parse(date).strftime(format)

def warn(message, severity = 1, borders = True):
    color_sequence = CLIColorSequences.failure if severity > 1 else CLIColorSequences.warning
    print_message(message, color_sequence, borders)

def success(message, borders = False):
    color_sequence = CLIColorSequences.ok_green
    print_message(message, color_sequence, borders)

def print_message(message, color_sequence, borders = False):
    min_line_width = 30
    max_line_width = 120
    message_width = len(message) if len(message) < max_line_width else max_line_width
    message_width = message_width if message_width > min_line_width else min_line_width
    if borders:
        print(color_sequence + ('*' * message_width) + CLIColorSequences.end_code)
    if len(message) > message_width:
        chunks, chunk_size = len(message), max_line_width
        messages = [ message[i:i+chunk_size] for i in range(0, chunks, max_line_width) ]
        message = "\n".join(messages)
    print(color_sequence + str(message) + CLIColorSequences.end_code)
    if borders:
        print(color_sequence + ('*' * message_width) + CLIColorSequences.end_code)

class CLIColorSequences:
    header = '\033[95m'
    ok_blue = '\033[94m'
    ok_green = '\033[92m'
    warning = '\033[93m'
    failure = '\033[91m'
    end_code = '\033[0m'
    bold = '\033[1m'
    underline = '\033[4m'
