PYTHON ?= ../../../env/bin/python

.PHONY: start-worker load starter test

start-worker:
	PYTHONPATH=. exec $(PYTHON) -m valet.worker

load:
	PYTHONPATH=. exec $(PYTHON) -m valet.load_simulator

starter:
	PYTHONPATH=. exec $(PYTHON) -m valet.starter

test:
	PYTHONPATH=. exec $(PYTHON) -m pytest tests/ -v
