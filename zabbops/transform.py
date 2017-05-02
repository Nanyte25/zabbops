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

def instance_to_host(instance, enabled=False, groups=None, templates=None, macros=None):
    """Converts the given EC2 Instance to a Zabbix Host"""

    status = '0' if enabled else '1'
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
            host['name'] = tag['Value']
            host['inventory']['name'] = tag['Value']
        elif key == 'description':
            host['description'] = tag['Value']

        host['macros'].append(tag_to_macro(tag))

    return host
