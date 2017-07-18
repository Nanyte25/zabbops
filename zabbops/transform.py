"""
Transform contains primitives for transforming AWS API objects into Zabbix API
objects.
"""

from re import sub

def get_tag_by_key(instance, key):
    """Returns the value of the given EC2 Instance Tag or None"""

    for tag in instance['Tags']:
        if key == tag['Key']:
            return tag['Value']

    return None

def tag_to_macro(tag, prefix='$EC2_TAG_'):
    """Converts the given EC2 Tag to a Zabbix User Macro"""

    macro = tag['Key'].upper()
    macro = sub(r'[^A-Z0-9]+', '_', macro)
    macro = sub(r'_{2,}', '_', macro)
    return {
        'macro': '{' + prefix + macro + '}',
        'value': tag['Value']
    }

def state_to_status(state):
    """Converts an EC2 Instance state to a Zabbix Host status."""

    # see: http://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_InstanceState.html
    if state in ('shutting-down', 'terminated', 'stopping', 'stopped'):
        return 1

    if state in ('running', 'pending'):
        return 0

    raise ValueError('Unrecognised EC2 state: {}'.format(state))

def instance_to_host(instance, groups=None, templates=None, macros=None):
    """Converts the given EC2 Instance to a Zabbix Host"""

    status = state_to_status(instance['State']['Name'])
    groups = groups or []
    templates = templates or []
    macros = macros or []

    host = {
        'host': instance['InstanceId'],
        'name': instance['InstanceId'],
        'status': status,
        'interfaces': [{
            'type': '1',
            'main': '1',
            'useip': '1',
            'ip': instance['PrivateIpAddress'],
            'dns': instance['PrivateDnsName'],
            'port': '10050'
        }],
        'inventory_mode': '0',
        'inventory': {
            'asset_tag': instance['InstanceId'],
            'hardware': instance['InstanceType'],
            'hw_arch': instance['Architecture'],
            'type': instance['ImageId'],
            'location': instance['Placement']['AvailabilityZone'],
            'macaddress_a': instance['NetworkInterfaces'][0]['MacAddress'],
            'host_networks': instance['VpcId'] + '\n' + instance['SubnetId']
        },
        'groups': groups,
        'templates': templates,
        'macros': macros
    }

    # append tags as macros
    for tag in instance['Tags']:
        key = tag['Key'].lower()
        if key == 'name':
            host['name'] = '{} ({})'.format(tag['Value'], instance['InstanceId'])
            host['inventory']['name'] = tag['Value']
        elif key == 'description':
            host['description'] = tag['Value']

        host['macros'].append(tag_to_macro(tag))

    return host

def host_diff(current, desired):
    """
    host_diff returns the difference between two Zabbix hosts in a format
    ready for posting to the host.update Zabbix API endpoint.
    """
    
    from copy import deepcopy

    is_diff = False
    diff = {
        'hostid': current['hostid'],
        'inventory': {},
    }

    # diff top-level fields
    # NOTE: we make an exception here for inventory_mode, as this field is not
    # returned by the Zabbix API and will therefore this always return a diff if
    # the field is defined in the desired state.
    top_fields = ('name', 'description', 'status')
    for field in top_fields:
        if str(current[field]) != str(desired[field]):
            is_diff = True
            diff[field] = desired[field]

    # diff inventory items
    for item in desired['inventory']:
        if (item not in current['inventory'] or
                current['inventory'][item] != desired['inventory'][item]):
            diff['inventory'][item] = desired['inventory'][item]
            is_diff = True

    # diff groups
    # NOTE: groups cannot be updated in patches. The diff must contain all
    # existing groups to prevent them being unlinked. Desired groups must be
    # provided in form {'groupid': <groupid>}
    current_groups = sorted(current['groups'], key=lambda x: x['groupid'])
    desired_groups = sorted(desired['groups'], key=lambda x: x['groupid'])
    if len(current_groups) != len(desired_groups):
        is_diff = True
        diff['groups'] = deepcopy(desired['groups'])
    else:
        for i in range(0, len(desired_groups)):
            if current_groups[i]['groupid'] != desired_groups[i]['groupid']:
                is_diff = True
                diff['groups'] = deepcopy(desired['groups'])
                break

    if is_diff:
        return diff
    return None