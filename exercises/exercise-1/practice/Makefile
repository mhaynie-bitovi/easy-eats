PYTHON ?= ../../../env/bin/python

.PHONY: worker load test

worker:
	PYTHONPATH=. exec $(PYTHON) -m valet.worker

load:
	PYTHONPATH=. exec $(PYTHON) -m valet.load_simulator

test:
	PYTHONPATH=. exec $(PYTHON) -m pytest tests/ -v
