from .transform import instance_to_host, host_diff

RFC_2822 = '%a, %d %b %Y %T %z'

class Configurator(object):
    """
    Configurator is an opinionated wrapper for py-zabbix that includes functions
    to update Zabbix configuration, using AWS API objects as input.
    """

    def __init__(self, api=None):
        from logging import getLogger
        from os import environ
        from pyzabbix import ZabbixAPI

        self._api = api

        # memoizing cache (no lifetime management)
        self._cache = {
            'hosts': {},
            'hostids': {},
            'groupids': {},
            'templateids': {}
        }

        self.logger = getLogger('zabbops')

        if not self._api:
            # connect using environment variables
            config = {}
            keys = [key for key in environ if key.startswith('ZABBIX_')]
            for key in keys:
                config[key[7:].lower()] = environ[key]

            self._api = ZabbixAPI(**config)

    def get_host(self, instance, by_field='host', raise_missing=True):
        """
        Returns the Zabbix Host for the given AWS EC2 Instance if it exists.
        """

        instanceid = instance['InstanceId']
        if instanceid in self._cache['hostids']:
            hostid = self._cache['hostids'][instanceid]
            if hostid in self._cache['hosts']:
                return self._cache['hosts'][hostid]

        response = self._api.do_request('host.get', {
            'filter': {by_field: [instanceid]},
            'output': 'extend',
            'selectGroups': 'extend',
            'selectInterfaces': 'extend',
            'selectInventory': 'extend',
            'selectMacros': 'extend',
        })

        if not response['result']:
            if raise_missing:
                raise Exception('Zabbix Host not found: {}'.format(instanceid))
            return None

        host = response['result'][0]
        hostid = host['hostid']
        self._cache['hostids'][instanceid] = hostid
        self._cache['hosts'][hostid] = host
        self.logger.debug('Lookup host for %s: %s', instanceid, hostid)
        return host


    def get_hostid(self, instance, by_field='host', raise_missing=True):
        """
        Returns the Zabbix Host ID of the given AWS EC2 Instance.
        """

        instanceid = instance['InstanceId']
        if instanceid in self._cache['hostids']:
            return self._cache['hostids'][instanceid]

        response = self._api.do_request('host.get', {
            'filter': {by_field: [instanceid]}
        })

        if not response['result']:
            if raise_missing:
                raise Exception('Zabbix Host not found: {}'.format(instanceid))
            return None

        hostid = response['result'][0]['hostid']
        self._cache['hostids'][instanceid] = hostid
        self.logger.debug('Looked up hostid for %s: %s', instanceid, hostid)
        return hostid

    def get_group_id(self, group_name, create_missing=False):
        """
        Returns the ID of the given Zabbix Host Group name.
        """

        if group_name in self._cache['groupids']:
            return self._cache['groupids'][group_name]

        response = self._api.do_request('hostgroup.get', {'filter': {'name': group_name}})
        if not response['result']:
            if not create_missing:
                return None

            response = self._api.do_request('hostgroup.create', {'name': group_name})
            return response['result']['groupids'][0]

        groupid = response['result'][0]['groupid']
        self._cache['groupids'][group_name] = groupid
        self.logger.debug('Looked up groupid for \'%s\': %s', group_name, groupid)
        return groupid

    def get_template_id(self, template_name, create_missing=False):
        """
        Returns the ID of the given Zabbix Template name.
        """

        if template_name in self._cache['templateids']:
            return self._cache['templateids'][template_name]

        response = self._api.do_request('template.get', {'filter': {'host': template_name}})
        if not response['result']:
            if not create_missing:
                return None

            groupid = self.get_group_id('Templates')
            response = self._api.do_request('template.create', {
                'host': template_name,
                'name': template_name,
                'groups': [{'groupid': groupid}]
            })
            return response['result']['templateids'][0]

        templateid = response['result'][0]['templateid']
        self._cache['templateids'][template_name] = templateid
        self.logger.debug('Looked up templateid for \'%s\': %s', template_name, templateid)
        return templateid

    def append_groups(self, host, groups, create_missing=True):
        """
        Append the given groups (by name) to a Zabbix Host. If create_missing is
        true, each group will be created if it does not already exist in Zabbix.
        """

        if not groups:
            return

        for group in groups:
            groupid = self.get_group_id(group, create_missing)
            host['groups'].append({'groupid': groupid})

    def append_templates(self, host, templates, create_missing=True):
        """
        Append the given templates (by name) to a Zabbix Host. If create_missing
        is true, each templates will be created if it does not already exist in
        Zabbix.
        """

        if not templates:
            return

        for template in templates:
            templateid = self.get_template_id(template, create_missing)
            host['templates'].append({'templateid': templateid})

    def upsert_host(self, instance, groups=None, templates=None):
        """
        Create a new Zabbix Host or update one if it already exists for the
        given AWS EC2 Instance.
        """

        # lookup existing Host - it would make more sense to simply create the
        # new host and respond to an 'already exists' error by subsequently
        # updating the Host if required. Unfortunately there is no way to
        # deterministically tell which error Zabbix returned. Would could search
        # for known strings, but this is not resilient to code releases.
        current = self.get_host(instance, raise_missing=False)
        if current is None:
            return self.create_host(instance, groups=groups, templates=templates)
        hostid = current['hostid']

        # determine desired state
        desired = instance_to_host(instance)
        self.append_groups(desired, groups)
        self.append_templates(desired, templates)

        # compute diff
        diff = host_diff(current, desired)
        if not diff:
            return {
                'hostid': hostid,
                'message': 'No changes for Zabbix Host {} ({})'.format(
                    instance['InstanceId'], hostid),
            }

        # invalidate cache
        if hostid in self._cache['hosts']:
            del self._cache['hosts'][hostid]

        # send update
        response = self._api.do_request('host.update', diff)
        if response['result']['hostids'][0] != hostid:
            raise Exception('Unexpected hostid returned. Expected {}, got {}'.format(
                hostid, response['result']['hostids'][0]))

        return {
            'hostid': hostid,
            'diff': diff,
            'message': 'Updated Zabbix Host {} ({})'.format(instance['InstanceId'], hostid),
        }

    def create_host(self, instance, groups=None, templates=None):
        """
        Create a new Zabbix Host for the given AWS EC2 Instance.
        """

        host = instance_to_host(instance)
        self.append_groups(host, groups)
        self.append_templates(host, templates)

        response = self._api.do_request('host.create', host)
        hostid = response['result']['hostids'][0]
        self._cache['hostids'][instance['InstanceId']] = hostid
        return {
            'hostid': hostid,
            'message': 'Created Zabbix Host {} ({})'.format(
                instance['InstanceId'],
                hostid)
        }

    def toggle_host(self, instance, enable=True):
        """
        Enable or disable the given AWS EC2 Instance for monitoring in Zabbix.
        """

        # invalidate cache
        hostid = self.get_hostid(instance)
        if hostid in self._cache['hosts']:
            del self._cache['hosts'][hostid]

        status = 0 if enable else 1
        statuses = ['Enabled', 'Disabled']
        self._api.do_request('host.update', {
            'hostid': hostid,
            'status': str(status)
        })

        return {
            'hostid': hostid,
            'message': '{} Zabbix Host {} ({})'.format(
                statuses[status],
                instance['InstanceId'],
                hostid)
        }

    def archive_host(self, instance, group='Archive', reason=None, ignore_missing=False):
        """
        Disable the given AWS EC2 Instance in Zabbix and move it to the Archive
        Host Group.
        """

        from datetime import datetime

        # invalidate cache
        hostid = self.get_hostid(instance, raise_missing=not ignore_missing)
        if hostid is None and ignore_missing:
            return {
                'hostid': None,
                'message': 'Zabbix Host {} does not exist - may have been archived already'.format(
                    instance['InstanceId'])
            }
        if hostid in self._cache['hosts']:
            del self._cache['hosts'][hostid]

        # disable and move to archive group
        groupid = self.get_group_id(group, create_missing=True)
        self._api.do_request('host.update', {
            'hostid': hostid,
            'status': '1',
            'groups' : [{'groupid': groupid}]
        })

        # set archive macros
        atime = datetime.now().strftime(RFC_2822)
        self._api.do_request('usermacro.create', {
            'hostid': hostid,
            'macro': '{$ARCHIVE_DATE}',
            'value': atime
        })

        if reason:
            self._api.do_request('usermacro.create', {
                'hostid': hostid,
                'macro': '{$ARCHIVE_REASON}',
                'value': reason
            })

        return {
            'hostid': hostid,
            'message': 'Archived Zabbix Host {} ({}): {}'.format(
                instance['InstanceId'],
                hostid,
                reason or '<no reason given>')
            }

    def delete_host(self, instance):
        """
        Delete the given AWS EC2 Instance from Zabbix.
        """

        # invalidate cache
        hostid = self.get_hostid(instance)
        if hostid in self._cache['hosts']:
            del self._cache['hosts'][hostid]

        self._api.do_request('host.delete', [hostid])
        return {
            'hostid': hostid,
            'message': 'Deleted Zabbix Host {} ({})'.format(
                instance['InstanceId'],
                hostid)
        }
