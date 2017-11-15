import requests, textwrap

from datetime import datetime, timedelta
from pprint import pprint

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
        'Weekly': timedelta(days = 7),
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
                output = "{}) {} | metadata_modified = {}, but updates {}, making it STALE!".format(i,title,metadata_modified,package['frequency_publishing'])
                stale_packages[package_id] = {'output': output, 
                    'last_modified': metadata_modified,
                    'normalized_lateness': lateness.total_seconds()/
                                        publishing_period.total_seconds(),
                    'publishing_frequency': publishing_frequency,
                    'json_index': i,
                    'title': title,
                    }
                stale_count += 1
        packages_with_frequencies += 1 

# Sort stale packages by relative tardiness so the most recently tardy ones 
# appear at the bottom of the output and the most egregiously late ones
# at the top.
stale_ps_sorted = sorted(stale_packages.iteritems(), 
                        key=lambda (k,v): -v['normalized_lateness'])
print("\nDatasets by Staleness: ")
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
    print(fmt.format(v['title'],v['normalized_lateness'],
        last_modified_date,v['publishing_frequency']))

print("=========================================================================\n")

coda = "Out of {} packages, only {} have specified publication frequencies. {} are stale (past their refresh-by date), according to the metadata_modified field.".format(len(packages),packages_with_frequencies,stale_count)
print(textwrap.fill(coda,70))
