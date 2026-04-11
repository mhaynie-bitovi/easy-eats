PYTHON ?= ../../../env/bin/python
DEPLOYMENT_NAME ?= valet-deploy
BUILD_ID ?= v1

.PHONY: start-worker load test

start-worker:
	TEMPORAL_DEPLOYMENT_NAME=$(DEPLOYMENT_NAME) TEMPORAL_WORKER_BUILD_ID=$(BUILD_ID) PYTHONPATH=. exec $(PYTHON) -m valet.worker

load:
	PYTHONPATH=. exec $(PYTHON) -m valet.load_simulator

test:
	PYTHONPATH=. exec $(PYTHON) -m pytest tests/ -v
