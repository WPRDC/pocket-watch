from datetime import datetime
import ckanapi, json, sys
from dateutil import parser

import traceback
from notify import send_to_slack
from leash import fill_bowl, empty_bowl, initially_leashed

def get_metadata(site,resource_id,API_key=None):
    metadata = ckan.action.resource_show(id=resource_id)

    return metadata

def create_resource_parameter(site,resource_id,parameter,value,API_key):
    """Creates one parameter with the given value for the specified
    resource."""
    success = False
    try:
        ckan = ckanapi.RemoteCKAN(site, apikey=API_key)
        payload = {}
        payload['id'] = resource_id
        payload[parameter] = value
        #For example,
        #   results = ckan.action.resource_patch(id=resource_id, url='#', url_type='')
        results = ckan.action.resource_patch(**payload)
        print(results)
        print("Created the parameter {} with value {} for resource {}".format(parameter, value, resource_id))
        success = True
    except:
        success = False
        exc_type, exc_value, exc_traceback = sys.exc_info()
        print("Error: {}".format(exc_type))
        lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        print(''.join('!!! ' + line for line in lines))

    return success

def set_resource_parameters_to_values(site,resource_id,parameters,new_values,API_key):
    """Sets the given resource parameters to the given values for the specified
    resource.

    This fails if the parameter does not currently exist. (In this case, use
    create_resource_parameter().)"""
    success = False
    try:
        ckan = ckanapi.RemoteCKAN(site, apikey=API_key)
        original_values = [get_resource_parameter(site,resource_id,p,API_key) for p in parameters]
        payload = {}
        payload['id'] = resource_id
        for parameter,new_value in zip(parameters,new_values):
            payload[parameter] = new_value
        #For example,
        #   results = ckan.action.resource_patch(id=resource_id, url='#', url_type='')
        results = ckan.action.resource_patch(**payload)
        print(results)
        print("* Changed the parameters {} from {} to {} on resource {} * ".format(parameters, original_values, new_values, resource_id))
        success = True
    except:
        success = False
        exc_type, exc_value, exc_traceback = sys.exc_info()
        print("Error: {}".format(exc_type))
        lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        print(''.join('!!! ' + line for line in lines))

    return success

def get_resource_parameter(site,resource_id,parameter=None,API_key=None):
    """Gets a CKAN resource parameter. If no parameter is specified, all metadata
    for that resource is returned."""
    # Some resource parameters you can fetch with this function are
    # 'cache_last_updated', 'package_id', 'webstore_last_updated',
    # 'datastore_active', 'id', 'size', 'state', 'hash',
    # 'description', 'format', 'last_modified', 'url_type',
    # 'mimetype', 'cache_url', 'name', 'created', 'url',
    # 'webstore_url', 'mimetype_inner', 'position',
    # 'revision_id', 'resource_type'
    # Note that 'size' does not seem to be defined for tabular
    # data on WPRDC.org. (It's not the number of rows in the resource.)
    try:
        ckan = ckanapi.RemoteCKAN(site, apikey=API_key)
        metadata = get_metadata(ckan,resource_id,API_key)
        if parameter is None:
            return metadata
        else:
            return metadata[parameter]
    except:
        raise RuntimeError("Unable to obtain resource parameter '{}' for resource with ID {}".format(parameter,resource_id))

def get_package_parameter(site,package_id,parameter=None,API_key=None):
    """Gets a CKAN package parameter. If no parameter is specified, all metadata
    for that package is returned."""
    # Some package parameters you can fetch from the WPRDC with
    # this function are:
    # 'geographic_unit', 'owner_org', 'maintainer', 'data_steward_email',
    # 'relationships_as_object', 'access_level_comment',
    # 'frequency_publishing', 'maintainer_email', 'num_tags', 'id',
    # 'metadata_created', 'group', 'metadata_modified', 'author',
    # 'author_email', 'state', 'version', 'department', 'license_id',
    # 'type', 'resources', 'num_resources', 'data_steward_name', 'tags',
    # 'title', 'frequency_data_change', 'private', 'groups',
    # 'creator_user_id', 'relationships_as_subject', 'data_notes',
    # 'name', 'isopen', 'url', 'notes', 'license_title',
    # 'temporal_coverage', 'related_documents', 'license_url',
    # 'organization', 'revision_id'
    try:
        ckan = ckanapi.RemoteCKAN(site, apikey=API_key)
        metadata = ckan.action.package_show(id=package_id)
        if parameter is None:
            return metadata
        else:
            return metadata[parameter]
    except:
        raise RuntimeError("Unable to obtain package parameter '{}' for package with ID {}".format(parameter,package_id))

def set_package_parameters_to_values(site,package_id,parameters,new_values,API_key):
    success = False
    try:
        ckan = ckanapi.RemoteCKAN(site, apikey=API_key)
        original_values = [get_package_parameter(site,package_id,p,API_key) for p in parameters]
        payload = {}
        payload['id'] = package_id
        for parameter,new_value in zip(parameters,new_values):
            payload[parameter] = new_value
        results = ckan.action.package_patch(**payload)
        #print(results)
        print("Changed the parameters {} from {} to {} on package {}".format(parameters, original_values, new_values, package_id))
        success = True
    except:
        success = False
        exc_type, exc_value, exc_traceback = sys.exc_info()
        print("Error: {}".format(exc_type))
        lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        print(''.join('!!! ' + line for line in lines))

    return success

def query_resource(site,query,API_key=None):
    # Use the datastore_search_sql API endpoint to query a CKAN resource.

    # Note that this doesn't work for private datasets.
    # The relevant CKAN GitHub issue has been closed.
    # https://github.com/ckan/ckan/issues/1954
    ckan = ckanapi.RemoteCKAN(site, apikey=API_key)
    response = ckan.action.datastore_search_sql(sql=query)
    # A typical response is a dictionary like this
    #{u'fields': [{u'id': u'_id', u'type': u'int4'},
    #             {u'id': u'_full_text', u'type': u'tsvector'},
    #             {u'id': u'pin', u'type': u'text'},
    #             {u'id': u'number', u'type': u'int4'},
    #             {u'id': u'total_amount', u'type': u'float8'}],
    # u'records': [{u'_full_text': u"'0001b00010000000':1 '11':2 '13585.47':3",
    #               u'_id': 1,
    #               u'number': 11,
    #               u'pin': u'0001B00010000000',
    #               u'total_amount': 13585.47},
    #              {u'_full_text': u"'0001c00058000000':3 '2':2 '7827.64':1",
    #               u'_id': 2,
    #               u'number': 2,
    #               u'pin': u'0001C00058000000',
    #               u'total_amount': 7827.64},
    #              {u'_full_text': u"'0001c01661006700':3 '1':1 '3233.59':2",
    #               u'_id': 3,
    #               u'number': 1,
    #               u'pin': u'0001C01661006700',
    #               u'total_amount': 3233.59}]
    # u'sql': u'SELECT * FROM "d1e80180-5b2e-4dab-8ec3-be621628649e" LIMIT 3'}
    data = response['records']
    return data


def find_extremes(resource_id,field):
    from credentials import site, ckan_api_key as API_key

    toggle = initially_leashed(resource_id)
    if toggle:
        fill_bowl(resource_id)
    query = 'SELECT min("{}") AS smallest, max("{}") as biggest FROM "{}" LIMIT 1'.format(field,field,resource_id)
    record = query_resource(site=site, query=query, API_key=API_key)[0]
    if toggle: # Strictly speaking this may not be necessary, as bowl-emptying may have no effect on some resources.
        empty_bowl(resource_id)
    return record['smallest'], record['biggest']


def fix_temporal_coverage(package_id,time_field_lookup,test=False):
    from credentials import site, ckan_api_key as API_key

    parameter = "temporal_coverage"
    initial_value = get_package_parameter(site,package_id,parameter=parameter,API_key=API_key)
    title = get_package_parameter(site,package_id,parameter="title",API_key=API_key)
    print("Initial temporal coverage of {} = {}".format(title,initial_value))
    # Find all resources in package that have datastores.
    very_first = datetime(3000,4,13)
    very_last = datetime(1000,5,14)
    resources = get_package_parameter(site,package_id,'resources',API_key)
    for r in resources:
        if r['datastore_active']:
            resource_id = r['id']
            if resource_id in time_field_lookup:
                time_field = time_field_lookup[resource_id]
                first, last = find_extremes(resource_id,time_field)
                first = parser.parse(first)
                last = parser.parse(last)
                if first < very_first:
                    very_first = first
                if last > very_last:
                    very_last = last

    temporal_coverage = "{}/{}".format(very_first.date(),very_last.date())
    print("  New temporal coverage for {} ({}) = {}".format(title,package_id,temporal_coverage))
    # Alter metadata for package
    if initial_value != temporal_coverage:
        if not test:
            set_package_parameters_to_values(site,package_id,[parameter],[temporal_coverage],API_key)
        else:
            print("  No update made because this is just a test.")
    else:
        print("  No update needed. (Existing temporal coverage matches current temporal coverage.)")

def main(just_testing):
    # [ ] Maybe change very_last to an empty string if it is reasonably close to the present.
    from credentials import transactions_package_id, site, ckan_api_key as API_key

    # Get all packages and resources
    ckan = ckanapi.RemoteCKAN(site,apikey=API_key) # Without specifying
    # the apikey field value, the next line will only return non-private packages.
    try:
        packages = ckan.action.current_package_list_with_resources(limit=999999)
    except:
        packages = ckan.action.current_package_list_with_resources(limit=999999)

    # For packages where all tabular data has the same schema, the time_field metadata
    # field could be specified in the package-level metadata, like this:
    #  u'extras': [{u'key': u'time_field', u'value': u'CREATED_ON'}]

    # However, eventually, we will want to have a standardized column (with datetime
    # in a standard format, as well as a standard field name.

    # The other issue is that there are some packages which have different time fields
    # for different resources.
    #       Here, the time_field could be a JSON encoded look-up table, by resource ID.
    #           time_field = {"76fda9d0-69be-4dd5-8108-0de7907fc5a4": "CREATED_ON"}

    # Further, there are some tables where there are multiple time fields, and it may
    # not be clear which is the best one to use as the standard time field. The default
    # should probably be the one that is most representative of the datetime of the event
    # represented by that row.
    for package in packages:
        if 'extras' in package:
            extras_list = package['extras']
            # The format is like this:
            #       u'extras': [{u'key': u'dcat_issued', u'value': u'2014-01-07T15:27:45.000Z'}, ...
            # not a dict, but a list of dicts.
            extras = {d['key']: d['value'] for d in extras_list}
            #if 'dcat_issued' not in extras:
            if 'time_field' in extras:
                time_field_lookup = json.loads(extras['time_field'])
                fix_temporal_coverage(package['id'],time_field_lookup,just_testing)

from credentials import production
try:
    if __name__ == '__main__':
        just_testing = False
        if len(sys.argv) > 1:
            if sys.argv[1] == 'True':
                just_testing = True
            elif sys.argv[1] == 'False':
                just_testing = False
        main(just_testing=just_testing)
except:
    e = sys.exc_info()[0]
    msg = "Error: {} : \n".format(e)
    exc_type, exc_value, exc_traceback = sys.exc_info()
    lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
    msg = ''.join('!! ' + line for line in lines)
    msg = "watchdog.py failed for some reason.\n" + msg
    print(msg) # Log it or whatever here
    if not just_testing and production:
        send_to_slack(msg,username='watchdog',channel='@david',icon=':doge:')
