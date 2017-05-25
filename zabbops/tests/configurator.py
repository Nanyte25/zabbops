"""
Tests for zabbops module
"""

import unittest
from ..configurator import Configurator

# Example EC2 Instance
INSTANCE = {
    'InstanceId': 'i-deadbeef',
    'PrivateIpAddress': '172.16.0.1',
    'PrivateDnsName': 'ip-172-16-0-1.us-west-1.compute.internal',
    'InstanceType': 't2.micro',
    'Architecture': 'x86_64',
    'ImageId': 'ami-deadbeef',
    'Placement': {
        'AvailabilityZone': 'us-west-1a'
    },
    'NetworkInterfaces': [{
        'MacAddress': 'de:ad:be:ef:ca:fe'
    }],
    'VpcId': 'vpc-deadbeef',
    'SubnetId': 'subnet-deadbeef',
    'Tags': [
        {'Key': 'Name', 'Value': 'Ec2TestInstance'},
        {'Key': 'Description', 'Value': 'Zabbops EC2 Test Instance'},
        {'Key': 'Environment', 'Value': 'Test'}
    ]
}

class ConfiguratorTests(unittest.TestCase):
    """
    Tests for the Zabbix Lambda handlers.

    WARNING: Tests will modify the given instance configuration in Zabbix, but
    will not make any changes to AWS.
    """

    def test_001_create_host(self):
        """
        Create a Zabbix Host for a new EC2 Instance.
        """

        groups = ['Linux servers', 'Virtual machines']
        templates = ['Template OS Linux', 'Template ICMP Ping']
        configurator = Configurator()
        configurator.create_host(INSTANCE, False, groups, templates)
        response = configurator._api.do_request('host.get', {
            'filter': {
                'host': INSTANCE['InstanceId']
            },
            'selectGroups': 'extend',
            'selectInterfaces': 'extend',
            'selectInventory': 'extend',
            'selectMacros': 'extend',
            'selectParentTemplates': 'extend'
        })
        host = response['result'][0]
        self.assertEqual(host['host'], INSTANCE['InstanceId'])
        self.assertEqual(host['name'], '{} ({})'.format(INSTANCE['Tags'][0]['Value'], INSTANCE['InstanceId']))
        self.assertEqual(host['status'], '1')
        self.assertEqual(host['description'], INSTANCE['Tags'][1]['Value'])

    def test_002_toggle_host(self):
        """
        Enable and disable a Zabbix Host.
        """

        configurator = Configurator()
        configurator.toggle_host(INSTANCE, enable=True)
        response = configurator._api.do_request('host.get', {
            'filter': {'host': INSTANCE['InstanceId']},
            'output': ['status']
        })
        self.assertEqual(response['result'][0]['status'], '0')

        configurator.toggle_host(INSTANCE, enable=False)
        response = configurator._api.do_request('host.get', {
            'filter': {'host': INSTANCE['InstanceId']},
            'output': ['status']
        })
        self.assertEqual(response['result'][0]['status'], '1')

    def test_003_archive_host(self):
        """
        Archive a Zabbix Host for a terminated EC2 Instance.
        """

        ret = Configurator().archive_host(INSTANCE, reason='Testing')
        self.assertIsNotNone(ret)

    def test_004_delete_host(self):
        """
        Delete a Zabbix Host for a terminated EC2 Instance.
        """

        ret = Configurator().delete_host(INSTANCE)
        self.assertIsNotNone(ret)
