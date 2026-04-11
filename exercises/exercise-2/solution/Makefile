PYTHON ?= ../../../env/bin/python
DEPLOYMENT_NAME ?= valet-deploy
BUILD_ID ?= 1.0

.PHONY: start-worker load starter test

start-worker:
	TEMPORAL_DEPLOYMENT_NAME=$(DEPLOYMENT_NAME) TEMPORAL_WORKER_BUILD_ID=$(BUILD_ID) PYTHONPATH=. exec $(PYTHON) -m valet.worker

load:
	PYTHONPATH=. exec $(PYTHON) -m valet.load_simulator

starter:
	PYTHONPATH=. exec $(PYTHON) -m valet.starter

test:
	PYTHONPATH=. exec $(PYTHON) -m pytest tests/ -v
