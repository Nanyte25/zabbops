from setuptools import setup

setup(name='zabbops',
      version='1.1',
      description='Zabbix/AWS orchestration',
      url='http://github.com/cavaliercoder/zabbops',
      author='Ryan Armstrong',
      author_email='ryan@cavaliercoder.com',
      license='GPLv3',
      packages=['zabbops'],
      install_requires=[
          'py-zabbix',
      ],
      zip_safe=False)
