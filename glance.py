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
# (This is not true. metadata_modified is being explicitly changed
# by the ETL framework. For that matter, the effect of ETL jobs need
# not even show up in the last_modified field of altered resources.
# I'm pretty sure it's the job of the ETL framework to make those change
# as well.)

# This could be done either by tagging those resources
# (e.g., with "updates_hourly") or by hard-coding resource IDs
# that need to be tracked.

# [ ] Implement "updates_monthly" tracking of liens resources.

import os, sys, json, requests, textwrap, traceback

from datetime import datetime, timedelta
from dateutil import parser
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

def pluralize(word,xs,return_count=True,count=None):
    # This version of the pluralize function has been modified
    # to support returning or not returning the count
    # as part of the conditionally pluralized noun.
    if xs is not None:
        count = len(xs)
    if return_count:
        return "{} {}{}".format(count,word,'' if count == 1 else 's')
    else:
        return "{}{}".format(word,'' if count == 1 else 's')

def print_table(stale_ps_sorted):
    if sys.stdout.isatty():
        #Running from command line
        rows, columns = get_terminal_size()

        template = "{{:<40.40}}  {}  {{:<10.10}}  {{:<12.12}}"
        fmt = template.format("{:>10.14}")
        used_columns = len(fmt.format("aardvark","bumblebee",
            "chupacabra","dragon","electric eel","flying rod"))

        publisher_length = 23
        if columns > used_columns + publisher_length + len("harvested"):
            template += " {{" + ":<{}.{}".format(publisher_length,publisher_length) + "}}" + " {{:<9.9}}"
            fmt = template.format("{:>10.14}")
            used_columns = len(fmt.format("aardvark","bumblebee",
                "chupacabra","dragon","electric eel","flying rod",
                "gorilla"))
        border = "{}".format("="*used_columns)
        print(fmt.format("","Cycles", "metadata_","publishing","","Upload"))
        print(fmt.format("Title","late", "modified","frequency","Publisher","Method"))
        print(border)
        fmt = template.format("{:>10.2f}")
        for k,v in stale_ps_sorted:
            last_modified_date = datetime.strftime(v['last_modified'], "%Y-%m-%d")
            fields = [v['title'],v['cycles_late'],
                last_modified_date,v['publishing_frequency'],v['publisher'],v['upload_method']]

            print(fmt.format(*fields))
        print("{}\n".format(border))

def infer_upload_method(package):
    """This function tries to figure out what upload method
    is involved in publishing data to this package. Since
    the _etl tag is a package-level tag, for the purposes
    of pocket-watch, this is a pretty good way of
    determining which upload method is involved in a package
    becoming stale.

    Most of this code was borrowed from dataset-tracker."""
    tag_dicts = package['tags']
    tags = [td['name'] for td in tag_dicts]
    if '_etl' in tags:
        # This is the package-level tag, so not every resource inside will be ETLed.
        # For the Air Quality dataset, Excel, CSV, and PDF files all seem to be ETLed.
        # Let's exclude data dictionaries:
        #if re.search('data dictionary',resource_name,re.IGNORECASE) is not None or resource['format'] in ['HTML','html']:
        #    loading_method = 'manual'
        #else:
        #    loading_method = 'etl'
        loading_method = 'etl'
    elif '_harvested' in tags:
        loading_method = 'harvested'
    else:
        r_names = [r['name'] if 'name' in r else 'Unnamed resource' for r in package['resources']]
        if 'Esri Rest API' in r_names:
            loading_method = 'harvested'
        else:
            loading_method = 'manual'
            # This package is probably all manually uploaded data.
    return loading_method

def temporal_coverage_end(package):
    """Returns a string representing the end date (or None)."""
    if 'extras' not in package:
        return None
    extras_list = package['extras']
    # The format is like this:
    #       u'extras': [{u'key': u'dcat_issued', u'value': u'2014-01-07T15:27:45.000Z'}, ...
    # not a dict, but a list of dicts.
    extras = {d['key']: d['value'] for d in extras_list}
    #if 'dcat_issued' not in extras:
    if 'time_field' in extras:
        # Then it is a package that has a temporal_coverage metadata field that is automatatically updated,
        # and the end of this range can also be checked for lateness
        parameter = "temporal_coverage"
        if parameter in package:
            temporal_coverage = package[parameter]
        else:
            temporal_coverage = None
        try:
            start_date, end_date = temporal_coverage.split('/')
        except ValueError:
            end_date = None
        return end_date
    return None

def compute_lateness(extensions, package_id, publishing_period, reference_dt):
    lateness = datetime.now() - (reference_dt + publishing_period)
    if package_id in extensions.keys():
        if lateness.total_seconds() > 0 and lateness.total_seconds() < extensions[package_id]['extra_time'].total_seconds():
            title = extensions[package_id]['title']
            print("{} is technically stale ({} cycles late), but we're giving it a pass because either there may not have been any new data to upsert or the next day's ETL job should fill in the gap.".format(title,lateness.total_seconds()/publishing_period.total_seconds()))
        lateness -= extensions[package_id]['extra_time']
    return lateness


def main(mute_alerts = True):
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


    # Some datasets are showing up as stale for one day because
    # (for instance) the County doesn't post jail census data
    # on a given day to their FTP server; our ETL script runs
    # but it doesn't update the metadata_modified.

    # One better solution to this would be to create a package-
    # (and maybe also resource-) level metadata field called
    # etl_job_last_ran.

    # For now, I'm hard-coding in a few exceptions.
    extensions = {'d15ca172-66df-4508-8562-5ec54498cfd4': {'title': 'Allegheny County Jail Daily Census',
                    'extra_time': timedelta(days=1),
                    'actual_data_source_reserve': timedelta(days=15)},
                  '046e5b6a-0f90-4f8e-8c16-14057fd8872e': {'title': 'Police Incident Blotter (30 Day)',
                    'extra_time': timedelta(days=1)}
                }

    nonperiods = ['', 'As Needed', 'Not Updated (Historical Only)']

    packages_with_frequencies = 0
    stale_count = 0
    stale_packages = {}
    for i,package in enumerate(packages):
        if 'frequency_publishing' in package.keys():
            title = package['title']
            package_id = package['id']
            dataset_url = "https://data.wprdc.org/dataset/{}".format(package['name'])
            metadata_modified = datetime.strptime(package['metadata_modified'],"%Y-%m-%dT%H:%M:%S.%f")
            publishing_frequency = package['frequency_publishing']
            data_change_rate = package['frequency_data_change']
            publisher = package['organization']['title']

            temporal_coverage_end_date = temporal_coverage_end(package) # Check for 'time_field' and auto-updated temporal_coverage field

            if publishing_frequency in period:
                publishing_period = period[publishing_frequency]
            else:
                publishing_period = None
                if publishing_frequency not in nonperiods:
                    raise ValueError("{}) {}: {} is not a known publishing frequency".format(k,title,publishing_frequency))
            #print("{} ({}) was last modified {} (according to its metadata). {}".format(title,package_id,metadata_modified,package['frequency_publishing']))

            if publishing_period is not None:
                lateness = compute_lateness(extensions, package_id, publishing_period, metadata_modified)
                if temporal_coverage_end_date is not None:
                    temporal_coverage_end_dt = datetime.strptime(temporal_coverage_end_date, "%Y-%m-%d") + timedelta(days=1) # [ ] This has no time zone associated with it.
                    # [ ] Change this to use parser.parse to allow times to be included, but also think more carefully about adding that offset.

                    data_lateness = compute_lateness(extensions, package_id, publishing_period, temporal_coverage_end_dt)
                else:
                    data_lateness = timedelta(seconds=0)


                if lateness.total_seconds() > 0 or data_lateness.total_seconds() > 0: # Either kind of lateness triggers the listing of another stale package.
                    stale_packages[package_id] = {
                        'publishing_frequency': publishing_frequency,
                        'data_change_rate': data_change_rate,
                        'publisher': publisher,
                        'json_index': i,
                        'title': title,
                        'package_id': package_id,
                        'package_url': dataset_url,
                        'upload_method': infer_upload_method(package),
                        'url': dataset_url
                        }
                    if lateness.total_seconds() > 0:
                        stale_packages[package_id]['cycles_late'] = lateness.total_seconds()/publishing_period.total_seconds()
                        stale_packages[package_id]['last_modified'] = metadata_modified
                        stale_packages[package_id]['days_late'] = lateness.total_seconds()/(60.0*60*24)
                    else:
                        stale_packages[package_id]['cycles_late'] = 0
                        stale_packages[package_id]['last_modified'] = metadata_modified
                        stale_packages[package_id]['days_late'] = 0.0

                    #if temporal_coverage_end_date is not None:
                    if data_lateness.total_seconds() > 0:
                        stale_packages[package_id]['temporal_coverage_end'] = temporal_coverage_end_date # This is a string.
                        stale_packages[package_id]['data_cycles_late'] = data_lateness.total_seconds()/publishing_period.total_seconds()

                    # Describe the evidence that the package is stale.
                    output = "{}) {} updates {}".format(i,title,package['frequency_publishing'])
                    if lateness.total_seconds() > 0 and data_lateness.total_seconds() > 0:
                        output += " but metadata_modified = {} and temporal_coverage_end_date = {} making it DOUBLE STALE!".format(metadata_modified,temporal_coverage_end_date)
                    elif lateness.total_seconds() > 0:
                        output += " but metadata_modified = {} making it STALE!".format(metadata_modified)
                    elif data_lateness.total_seconds() > 0:
                        output += " but temporal_coverage_end_date = {} making it STALE!".format(temporal_coverage_end_date)
                    stale_packages[package_id]['output'] = output

                    stale_count += 1
            packages_with_frequencies += 1



    # Sort stale packages by relative tardiness so the most recently tardy ones
    # appear at the bottom of the output and the most egregiously late ones
    # at the top.
    #stale_ps_sorted = sorted(stale_packages.iteritems(), key=lambda(k,v): -v['cycles_late'])
           #Note that in Python 3, key=lambda(k,v): v['position'] must be written as key=lambda k_v: k_v[1]['position']
    stale_ps_sorted = sorted(stale_packages.items(), key=lambda k_v: -k_v[1]['cycles_late'])

    print("\nDatasets by Staleness: ")
    print_table(stale_ps_sorted)

    stale_ps_by_recency = sorted(stale_packages.items(), key=lambda k_v: -k_v[1]['days_late'])
    print("\n\nStale Datasets by Lateness: ")
    print_table(stale_ps_by_recency)

    stale_ps_by_data_lateness = {p_id: sp for p_id,sp in stale_packages.items() if 'temporal_coverage_end' in sp}
    stale_ps_by_data_lateness = sorted(stale_ps_by_data_lateness.items(), key=lambda k_v: -k_v[1]['data_cycles_late'])
    if len(stale_ps_by_data_lateness) > 0:
        print("\n\nStale Datasets by Data-Lateness: ")
        print_table(stale_ps_by_data_lateness)
    else:
        print("No datasets are stale by data-lateness.")


    coda = "Out of {} packages, only {} have specified publication frequencies. {} are stale (past their refresh-by date), according to the metadata_modified field.".format(len(packages),packages_with_frequencies,stale_count)
    print(textwrap.fill(coda,70))

    # Store list of stale packages in a JSON file as a record of the last
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

    wprdc_datasets = ['22fe57da-f5b8-4c52-90ea-b10591a66f90', # Liens
            'f2141a79-c0b9-4cf9-b4d2-d591b4aaa8e6' # Foreclosures
            ]

    if len(newly_stale) > 0:
        printable_stale_items = ["{} ({})".format(sp[1]['title'],sp[1]['package_url']) for sp in newly_stale]
        linked_stale_items = ["<{}|{}> ({})".format(sp[1]['package_url'],sp[1]['title'],sp[1]['upload_method']) for sp in newly_stale]
        includes_etl_string = " (includes ETL job)" if any([sp[1]['upload_method'] == 'etl' for sp in newly_stale]) else ""

        msg = "NEWLY STALE{}: {}".format(includes_etl_string, ', '.join(linked_stale_items)) # formatted for Slack
        printable_msg = "NEWLY STALE{}: {}".format(includes_etl_string, ', '.join(printable_stale_items))
        print(printable_msg)
        if not mute_alerts:
            send_to_slack(msg,username='pocket watch',channel='#stale-datasets',icon=':illuminati:')
            other_notifications = [
                {'publisher': 'Allegheny County', 'medium': 'Slack',
                'channel': '#county-stale-datasets',
                'slack_group': 'wprdc-and-friends',
                'slack-config': 'something'}
                ]

            for other in other_notifications:
                if other['publisher'] in [sp[1]['publisher'] for sp in newly_stale]:
                    publisher_stale_sets = []
                    for sp in newly_stale:
                        if other['publisher'] == sp[1]['publisher'] and sp[0] not in wprdc_datasets:
                            publisher_stale_sets.append(sp)

                    publisher_stale_ones = ["<{}|{}>".format(sp[1]['url'],sp[1]['title']) for sp in publisher_stale_sets]
                    if len(publisher_stale_ones) > 0:
                        printable_publisher_stale_ones = [sp[1]['title'] for sp in publisher_stale_sets]
                        multiple = len(publisher_stale_ones) != 1
                        publisher_msg = "Hey there! I just noticed {} newly stale {}: {}".format(len(publisher_stale_ones),pluralize("dataset",publisher_stale_ones,False), ', '.join(publisher_stale_ones))
                        #send_to_different_slack: wprdc-and-friends
                        print(publisher_msg)
                        send_to_slack(publisher_msg,username='pocket watch',channel='#county-stale-datasets',slack_group=other['slack_group'])
                        #send_to_slack(publisher_msg,username='pocket watch',channel='#boring-tests',slack_group=other['slack_group'])
        else:
            print("[Slack alerts are muted.]")


    store_as_json(currently_stale)

from credentials import production
try:
    if __name__ == '__main__':
        if len(sys.argv) == 1:
            main()
        else:
            if sys.argv[1] == 'True':
                mute_alerts = True
            elif sys.argv[1] == 'False':
                mute_alerts = False
            else:
                raise ValueError("{} is neither True nor False. It should be a boolean that sets the mute_alerts variable.".format(sys.argv[1]))
            main(mute_alerts = mute_alerts)
except:
    e = sys.exc_info()[0]
    msg = "Error: {} : \n".format(e)
    exc_type, exc_value, exc_traceback = sys.exc_info()
    lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
    msg = ''.join('!! ' + line for line in lines)
    msg = "pocket_watch/glance.py failed for some reason.\n" + msg
    print(msg) # Log it or whatever here
    if production:
        send_to_slack(msg,username='pocket watch',channel='@david',icon=':illuminati:')
