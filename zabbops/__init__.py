"""
Zabbops provides the ability to orchestrate Zabbix configuration using the
AWS EC2 and Lambda APIs (boto).
"""

from .configurator import Configurator
from .transform import get_tag_by_key, tag_to_macro, instance_to_host
from .handlers import KinesisStreamHandler

__version__ = '1.0.0'
