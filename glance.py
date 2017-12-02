# This script scans the current package list of a CKAN instance
# and finds the datasets that have not been updated on their
# self-identified schedule.

# Note that each resource has a 'last_modified' timestamp, which 
# could also be examined to study staleness. The alternate approach
# would be to compare the 'last_modified' timestamp of the most 
# recently modified resource with the nominal publication frequency
# and the current date.

# However, since changes to a resource's 'last_modified' timestamp
# seem to ripple upward, changing the timestamp of the package's
# 'metadata_modified' field, looking at 'last_modified' timestamps
# only seems necessary when multiple resources in a package need
# to be monitored to make sure they are all being updated.
# This could be done either by tagging those resources 
# (e.g., with "updates_hourly") or by hard-coding resource IDs
# that need to be tracked.

# [ ] Implement "updates_monthly" tracking of liens resources.

import os, json, requests, textwrap

from datetime import datetime, timedelta
from pprint import pprint

from notify import send_to_slack

def get_archive_path():
    # Change path to script's path for cron job.
    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    os.chdir(dname)
    last_scan_file = dname+'/last_scan.json'
    return last_scan_file

def store_as_json(output):
    last_scan_file = get_archive_path()
    with open(last_scan_file, 'w') as f:
        json.dump(output, f, ensure_ascii=True, indent = 4)

def load_from_json():
    last_scan_file = get_archive_path()
    with open(last_scan_file, 'r') as f:
        return json.load(f)

def get_terminal_size():
    rows, columns = os.popen('stty size', 'r').read().split()
    return int(rows), int(columns)

def print_table(stale_ps_sorted):
    rows, columns = get_terminal_size()

    template = "{{:<30.30}}  {}  {{:<10.10}}  {{:<12.12}}"
    fmt = template.format("{:>10.14}")
    used_columns = len(fmt.format("aardvark","bumblebee",
        "chupacabra","dragon","electric eel","flying rod"))

    publisher_length = 23
    if columns > used_columns + publisher_length:
        template += " {{" + ":<{}.{}".format(publisher_length,publisher_length) + "}}"
        fmt = template.format("{:>10.14}")
        used_columns = len(fmt.format("aardvark","bumblebee",
            "chupacabra","dragon","electric eel","flying rod"))
    border = "{}".format("="*used_columns)
    print(fmt.format("","Cycles", "metadata_","publishing",""))
    print(fmt.format("Title","late", "modified","frequency","Publisher"))
    print(border)
    fmt = template.format("{:>10.2f}")
    for k,v in stale_ps_sorted:
        last_modified_date = datetime.strftime(v['last_modified'], "%Y-%m-%d")
        fields = [v['title'],v['cycles_late'],
            last_modified_date,v['publishing_frequency'],v['publisher']]
            
        print(fmt.format(*fields))
    print("{}\n".format(border)


host = "data.wprdc.org"
url = "https://{}/api/3/action/current_package_list_with_resources?limit=999999".format(host)
r = requests.get(url)
response = r.json()
if not response['success']:
    msg = "Unable to get the package list."
    print(msg)
    raise ValueError(msg)

packages = response['result']

period = {'Annually': timedelta(days = 366),
        'Bi-Annually': timedelta(days = 183),
        'Quarterly': timedelta(days = 31+30+31),
        'Monthly': timedelta(days = 31),
        'Bi-Monthly': timedelta(days = 16),
        'Weekly': timedelta(days = 7),
        'Bi-Weekly': timedelta(days = 4),
        'Daily': timedelta(days = 1),
        'Hourly': timedelta(hours = 1),
        'Multiple Times per Hour': timedelta(minutes=30)}

nonperiods = ['', 'As Needed', 'Not Updated (Historical Only)']

packages_with_frequencies = 0
stale_count = 0
stale_packages = {}
for i,package in enumerate(packages):
    if 'frequency_publishing' in package.keys():
        title = package['title']
        package_id = package['id']
        metadata_modified = datetime.strptime(package['metadata_modified'],"%Y-%m-%dT%H:%M:%S.%f")
        publishing_frequency = package['frequency_publishing']
        data_change_rate = package['frequency_data_change']
        publisher = package['organization']['title']

        if publishing_frequency in period:
            publishing_period = period[publishing_frequency]
        else:
            publishing_period = None
            if publishing_frequency not in nonperiods:
                raise ValueError("{}) {}: {} is not a known publishing frequency".format(k,title,publishing_frequency))
        #print("{} ({}) was last modified {} (according to its metadata). {}".format(title,package_id,metadata_modified,package['frequency_publishing']))

        if publishing_period is not None:
            lateness = datetime.now() - (metadata_modified + publishing_period)
            if lateness.total_seconds() > 0:
                if data_change_rate not in nonperiods:
                    output = "{}) {} | metadata_modified = {}, but updates {}, making it STALE!".format(i,title,metadata_modified,package['frequency_publishing'])
                    stale_packages[package_id] = {'output': output, 
                        'last_modified': metadata_modified,
                        'cycles_late': lateness.total_seconds()/
                                            publishing_period.total_seconds(),
                        'publishing_frequency': publishing_frequency,
                        'data_change_rate': data_change_rate,
                        'publisher': publisher,
                        'json_index': i,
                        'title': title,
                        }
                    stale_count += 1
                else:
                    print("{} is not considered stale because its data change rate is {}".format(title,package['frequency_data_change']))
        packages_with_frequencies += 1 

# Sort stale packages by relative tardiness so the most recently tardy ones 
# appear at the bottom of the output and the most egregiously late ones
# at the top.
stale_ps_sorted = sorted(stale_packages.iteritems(), 
                        key=lambda (k,v): -v['cycles_late'])
print("\nDatasets by Staleness: ")
print_table(stale_ps_sorted)

stale_ps_by_recency = sorted(stale_packages.iteritems(), 
                        key=lambda (k,v): v['last_modified'])
print("\n\nStale Datasets by Refresh-by Date: ")
print_table(stale_ps_by_recency)


coda = "Out of {} packages, only {} have specified publication frequencies. {} are stale (past their refresh-by date), according to the metadata_modified field.".format(len(packages),packages_with_frequencies,stale_count)
print(textwrap.fill(coda,70))

# Store list of stale packages in a json file as a record of the last 
# glance (with the intent of sending notifications whenever new ones show up).
currently_stale = []

previously_stale = load_from_json()
previously_stale_ids = [x['id'] for x in previously_stale]
newly_stale = []
for sp in stale_ps_by_recency:
    r = {'id': sp[0], 'title': sp[1]['title']}
    currently_stale.append(r)
    
    if sp[0] not in previously_stale_ids:
        newly_stale.append(sp)

if len(newly_stale) > 0:
    msg = "NEWLY STALE: {}".format([sp[1]['title'] for sp in newly_stale])
    print(msg)
    send_to_slack(msg,username='pocket watch',channel='@david',icon=':illuminati:')

store_as_json(currently_stale)
