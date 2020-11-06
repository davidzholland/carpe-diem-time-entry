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

# Load the .env configuration
load_dotenv()

app_configs = {
    'cd_web': {
        'endpoints': {
            'add': 'https://tik-prd-usc-cd-cdweb-apiapp.azurewebsites.net/api/TimeEntry/AddTimeEntry'
        }
    },
    'cd_desktop': {
        'endpoints': {
            'add': 'https://cdmobile.fticonsulting.com/cdmobile/TimeKMSV.asp'
        }
    }
}
selected_app = None
access_token = os.getenv('accessToken')
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
    # testGET()
    # testPOST()
    set_app()
    set_date_range()
    submit_time_entries()

def testGET():
     # TODO: Remove this method
    headers = {
        "accept": "application/json",
        "Authorization": "Bearer " + access_token
    }
    url = 'https://tik-prd-usc-cd-cdweb-apiapp.azurewebsites.net/api/MonthView/Month/2020-11-01T00:00:00.000/Tkpr/21335'
    result = requests.get(url, headers=headers)
    print('test result: ', result)
    print('test result.text: ', result.text)
    print('test result.headers: ', result.headers)
    print('test result.status_code: ', result.status_code)

def testPOST():
     # TODO: Remove this method
    data = {"timekeeperId":"21335","startTime":"2020-11-03T08:00:00.000","endTime":"2020-11-03T16:00:00.000","offset":-6,"bestMatch":True,"overlapping":False,"exclusions":False}
    headers = {
        "Connection": "keep-alive",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
        "accept": "application/json",
        "Authorization": "Bearer " + access_token,
        "Delta": "ea33c7f05fffc88a2937de888a2c4ca7",
        # "Delta": uuid.uuid4().hex,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.183 Safari/537.36",
        "content-type": "application/json",
        "Origin": "https://us.carpe.tikit.com",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": "https://us.carpe.tikit.com/",
        "Accept-Language": "en-US,en;q=0.9,fr;q=0.8,zh-CN;q=0.7,zh;q=0.6,ja;q=0.5,af;q=0.4"
    }
    url = 'https://tik-prd-usc-cd-cdweb-apiapp.azurewebsites.net/api/TimeFinder/GetTimekeeperActivitiesCount'
    result = requests.post(url, headers=headers, data=data)
    print('test result: ', result)
    print('test result.text: ', result.text)
    print('test result.headers: ', result.headers)
    print('test result.status_code: ', result.status_code)
    exit()

def set_app():
    global selected_app
    selected_app = 'cd_web'
    if selected_app == 'cd_web' and False == confirm("Have you added your temporary access token to the .env file?"):
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
    today = datetime.date.today()
    if today.weekday() == 0:
        last_monday = today - datetime.timedelta(days=7)
    else:
        last_monday = today - datetime.timedelta(days=today.weekday())
    example_date_input = human_date(last_monday)
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
            exit() # TODO: Remove
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
    url = app_configs[selected_app]['endpoints']['add']
    data = prepare_data(entry)
    headers = prepare_headers(data, url)
    # submit request
    try:
        print('url: ', url)
        print('data: ', type(data), data)
        print('headers: ', headers)
        # exit() TODO: Remove this after development is completed
        result = requests.post(url, data=data, headers=headers)
        print('result: ', result.text)
        print('raw: ', result.raw)
        print('headers: ', result.headers)
        print('result: ', result)
        print('status_code: ', result.status_code)
    except requests.exceptions.RequestException as e:
        print('Submission failed with error code - %s.' % e.code)
        error_message = e.read()
        print(error_message)
        return False

def prepare_headers(data, url):
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
            "Connection": "keep-alive",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "accept": "application/json",
            "Authorization": "Bearer " + access_token,
            "Delta": "ea33c7f05fffc88a2937de888a2c4ca7",
            # "Delta": uuid.uuid4().hex, # TODO: Determine how to generate correct Delta
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.183 Safari/537.36",
            "content-type": "application/json",
            "Origin": "https://us.carpe.tikit.com",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://us.carpe.tikit.com/",
            "Accept-Language": "en-US,en;q=0.9,fr;q=0.8,zh-CN;q=0.7,zh;q=0.6,ja;q=0.5,af;q=0.4"
        }

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
                "roundTime": hours * 60 * 60, # Seconds
                "otherTime": 0,
                "remainingRawTime": 0,
                "remainingRoundTime": 0,
                "roundTimeDisplayValue": str(hours),
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
                "matterLanguage": "",
                "userCodes": {
                    # "Code1": entry['Task Code'], # Optional
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
            "defaultLangForSpellCheck": "en-US",
            "matterLanguage": ""
        }
        data = json.dumps(data)
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
