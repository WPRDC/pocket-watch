# This script scans the current package list of a CKAN instance
# and finds the datasets that have not been updated on their
# self-identified schedule.

# Note that each resource has a 'last_modified' timestamp, which 
# could also be examined to study staleness. The alternate approach
# would be to compare the 'last_modified' timestamp of the most 
# recently modified resource with the nominal publication frequency
# and the current date.

import os, json, requests, textwrap

from datetime import datetime, timedelta
from pprint import pprint

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

def print_table(stale_ps_sorted):
    template = "{{:<33.33}}  {}  {{:<10.10}}  {{:<12.12}}"
    fmt = template.format("{:>16.20}")
    #print(fmt.format("Title","Normalized lateness",
    #                "metadata_modified","publishing frequency"))

    print(fmt.format("","", "metadata_","publishing"))
    print(fmt.format("Title","Cycles late", "modified","frequency"))
    print("=========================================================================")
    #fmt = "{:<33.33} {:<20.3f} {:<10.10} {:<12.12}"
    fmt = template.format("{:>16.3f}")
    for k,v in stale_ps_sorted:
        last_modified_date = datetime.strftime(v['last_modified'], "%Y-%m-%d")
        print(fmt.format(v['title'],v['cycles_late'],
            last_modified_date,v['publishing_frequency']))
    print("=========================================================================\n")


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

print("NEWLY STALE: {}".format([sp[1]['title'] for sp in newly_stale]))

store_as_json(currently_stale)
