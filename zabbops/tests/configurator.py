"""
Tests for zabbops module
"""

import unittest
from copy import deepcopy
from ..configurator import Configurator

# Example EC2 Instance
INSTANCE = {
    'InstanceId': 'i-deadbeef',
    'State': {
        'Code': 80,
        'Name': 'stopped'
    },
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
    ],
}

GROUPS = ['Linux servers', 'Virtual machines']
ADD_GROUP = 'Hypervisors'
TEMPLATES = ['Template OS Linux', 'Template ICMP Ping']

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

        configurator = Configurator()
        ret = configurator.upsert_host(INSTANCE, groups=GROUPS, templates=TEMPLATES)
        self.assertIn('hostid', ret)
        self.assertIn('message', ret)
        self.assertRegexpMatches(ret['message'], r'^Created Zabbix Host i-.*$')

    def test_002_get_host(self):
        """
        Retrieve the created host.
        """

        host = Configurator().get_host(INSTANCE)
        self.assertEqual(host['host'], INSTANCE['InstanceId'])
        self.assertEqual(host['name'], '{} ({})'.format(INSTANCE['Tags'][0]['Value'], INSTANCE['InstanceId']))
        self.assertEqual(host['status'], '1')
        self.assertEqual(host['description'], INSTANCE['Tags'][1]['Value'])
        # TODO: more hosts checks

    def test_003_toggle_host(self):
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

    def test_004_upsert_existing(self):
        """
        No-op an existing Zabbix Host.
        """

        configurator = Configurator()
        ret = configurator.upsert_host(INSTANCE, groups=GROUPS, templates=TEMPLATES)
        self.assertIn('hostid', ret)
        self.assertIn('message', ret)
        self.assertRegexpMatches(ret['message'], r'^No changes for Zabbix Host i-.*$')

    def test_100_add_group(self):
        """
        Add a new group.
        """

        groups = deepcopy(GROUPS)
        groups.append(ADD_GROUP)

        configurator = Configurator()
        ret = configurator.upsert_host(INSTANCE, groups=groups, templates=TEMPLATES)
        
        self.assertRegexpMatches(ret['message'], r'^Updated Zabbix Host i-.*$')
        self.assertIn('hostid', ret)
        self.assertIn('diff', ret)

        # check for new group
        host = configurator.get_host(INSTANCE)
        groups = {}
        for group in host['groups']:
            groups[group['name']] = group['groupid']
        self.assertIn(ADD_GROUP, groups)

        self.assertEqual(len(host['groups']), len(GROUPS)+1)
        for group in GROUPS:
            self.assertIn(group, groups)

    def test_101_remove_group(self):
        """
        Remove a new group.
        """

        configurator = Configurator()
        ret = configurator.upsert_host(INSTANCE, groups=GROUPS, templates=TEMPLATES)
        self.assertRegexpMatches(ret['message'], r'^Updated Zabbix Host i-.*$')
        self.assertIn('hostid', ret)
        self.assertIn('diff', ret)

        # check new group is missing
        host = configurator.get_host(INSTANCE)
        groups = {}
        for group in host['groups']:
            groups[group['name']] = group['groupid']
        self.assertNotIn(ADD_GROUP, groups)

        self.assertEqual(len(host['groups']), len(GROUPS))
        for group in GROUPS:
            self.assertIn(group, groups)

#    def test_008_upsert_changes(self):
#        configurator = Configurator()
#        host = configurator.get_host(INSTANCE)
#
#        instance = deepcopy(INSTANCE)
#        instance['State']['Code'] = '16'
#        instance['State']['Name'] = 'running'
#        instance['Tags'][0]['Value'] = 'Ec2TestInstanceRenamed'
#        instance['Tags'][1]['Value'] = 'Updated description'
#        instance['InstanceType'] = 'm4.xlarge'
#        instance['PrivateIpAddress'] = '172.16.0.2'
#
#        ret = configurator.upsert_host(instance, groups=GROUPS, templates=TEMPLATES)
#        self.assertIn('hostid', ret)
#        self.assertIn('message', ret)
#        self.assertIn('diff', ret)
#        self.assertEqual(host['hostid'], ret['hostid'])
#        self.assertRegexpMatches(ret['message'], r'^Updated Zabbix Host i-.*$')
#
#        response = configurator._api.do_request('host.get', {
#            'hostids': host['hostid'],
#            'output': 'extend',
#            'selectInventory': 'extend',
#            'selectInterfaces': 'extend',
#        })
#        host = response['result'][0]
#        self.assertEqual(host['status'], '0')
#        self.assertEqual(host['name'], 'Ec2TestInstanceRenamed ({})'.format(INSTANCE['InstanceId']))
#        self.assertEqual(host['description'], 'Updated description')
#        self.assertEqual(host['inventory']['hardware'], 'm4.xlarge')
#        self.assertEqual(host['interfaces'][0]['ip'], '172.16.0.2')


    def test_200_archive_host(self):
        """
        Archive a Zabbix Host for a terminated EC2 Instance.
        """

        ret = Configurator().archive_host(INSTANCE, reason='Testing')
        self.assertIsNotNone(ret)

    def test_999_delete_host(self):
        """
        Delete a Zabbix Host for a terminated EC2 Instance.
        """

        ret = Configurator().delete_host(INSTANCE)
        self.assertIn('hostid', ret)
        self.assertIn('message', ret)
        self.assertRegexpMatches(ret['message'], r'^Deleted Zabbix Host i-.*$')
