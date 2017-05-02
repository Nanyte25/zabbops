all: check dist

check:
	python -m unittest zabbops.tests

dist:
	python setup.py sdist

install:
	pip install --upgrade .

clean:
	rm -vrf \
		zabbops/*.pyc \
		zabbops/tests/*.pyc \
		zabbops.egg-info/ \
		build/ \
		dist/

.PHONY: all check dist install clean
