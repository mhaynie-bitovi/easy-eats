PYTHON ?= ../../../env/bin/python
TAG ?= latest
IMAGE_NAME = valet-worker
WORKER_CONTROLLER_NAMESPACE = temporal-worker-controller
WORKER_CONTROLLER_VERSION ?= 0.24.0

.PHONY: setup build deploy status logs load start-worker test clean temporal-server

## temporal-server — start Temporal dev server locally (outside the cluster)
temporal-server:
	@echo "==> Starting Temporal dev server on localhost:7233 (UI on localhost:8233)..."
	temporal server start-dev --log-format pretty

## setup — start minikube, install Worker Controller (assumes Temporal dev server already running)
setup:
	@echo "==> Starting minikube..."
	minikube start --cpus=4 --memory=4096
	@echo "==> Installing Worker Controller CRDs..."
	kubectl create namespace $(WORKER_CONTROLLER_NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -
	helm upgrade --install temporal-worker-controller-crds \
		oci://docker.io/temporalio/temporal-worker-controller-crds \
		--version $(WORKER_CONTROLLER_VERSION) \
		--namespace $(WORKER_CONTROLLER_NAMESPACE)
	@echo "==> Installing cert-manager..."
	helm repo add jetstack https://charts.jetstack.io --force-update
	helm upgrade --install cert-manager jetstack/cert-manager \
		--namespace cert-manager \
		--create-namespace \
		--set crds.enabled=true \
		--wait
	@echo "==> Installing Worker Controller..."
	helm upgrade --install temporal-worker-controller \
		oci://docker.io/temporalio/temporal-worker-controller \
		--version $(WORKER_CONTROLLER_VERSION) \
		--namespace $(WORKER_CONTROLLER_NAMESPACE) \
		--set replicas=1 \
		--wait
	@echo "==> Setup complete. Verifying pods..."
	kubectl get pods -n $(WORKER_CONTROLLER_NAMESPACE)
	kubectl get crd | grep temporal

## build — build Docker image inside minikube's Docker daemon
build:
	@echo "==> Building image $(IMAGE_NAME):$(TAG) in minikube..."
	eval $$(minikube docker-env) && docker build -t $(IMAGE_NAME):$(TAG) .

## deploy — apply TemporalConnection + TemporalWorkerDeployment
deploy:
	@echo "==> Deploying valet worker..."
	kubectl apply -f k8s/temporal-connection.yaml
	kubectl apply -f k8s/valet-worker.yaml
	@echo "==> Deployed. Run 'make status' to check."

## status — show TemporalWorkerDeployment and Deployments
status:
	@echo "==> TemporalWorkerDeployments:"
	kubectl get twd
	@echo ""
	@echo "==> Deployments:"
	kubectl get deployments
	@echo ""
	@echo "==> Pods:"
	kubectl get pods

## logs — show Worker Controller logs
logs:
	kubectl logs -n $(WORKER_CONTROLLER_NAMESPACE) -l app.kubernetes.io/name=temporal-worker-controller --tail=100 -f

## start-worker — run the worker locally
start-worker:
	PYTHONPATH=. exec $(PYTHON) -m valet.worker

## load — run the load simulator locally (Temporal dev server must be running)
load:
	PYTHONPATH=. exec $(PYTHON) -m valet.load_simulator

## test — run tests
test:
	PYTHONPATH=. exec $(PYTHON) -m pytest tests/ -v

## clean — tear down everything
clean:
	@echo "==> Deleting worker deployment..."
	-kubectl delete -f k8s/valet-worker.yaml
	-kubectl delete -f k8s/temporal-connection.yaml
	@echo "==> Uninstalling Worker Controller..."
	-helm uninstall temporal-worker-controller -n $(WORKER_CONTROLLER_NAMESPACE)
	-helm uninstall temporal-worker-controller-crds -n $(WORKER_CONTROLLER_NAMESPACE)
	-helm uninstall cert-manager -n cert-manager
