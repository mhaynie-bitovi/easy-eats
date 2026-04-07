TAG ?= latest
IMAGE_NAME = valet-worker
TEMPORAL_NAMESPACE = temporal
WORKER_CONTROLLER_NAMESPACE = temporal-worker-controller
WORKER_CONTROLLER_VERSION ?= 0.24.0

.PHONY: setup build deploy status logs port-forward load clean

## setup — start minikube, deploy Temporal dev server, install Worker Controller
setup:
	@echo "==> Starting minikube..."
	minikube start --cpus=4 --memory=4096
	@echo "==> Creating temporal namespace..."
	kubectl create namespace $(TEMPORAL_NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -
	@echo "==> Deploying Temporal dev server..."
	kubectl apply -f k8s/temporal-dev-server.yaml
	kubectl rollout status deployment/temporal-dev-server -n $(TEMPORAL_NAMESPACE) --timeout=120s
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
	kubectl get pods -n $(TEMPORAL_NAMESPACE)
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

## port-forward — forward Temporal frontend and Web UI to localhost
port-forward:
	@echo "==> Forwarding Temporal frontend to localhost:7233 and Web UI to localhost:8080"
	@echo "    Press Ctrl+C to stop"
	kubectl port-forward -n $(TEMPORAL_NAMESPACE) svc/temporal-frontend 7233:7233 &
	kubectl port-forward -n $(TEMPORAL_NAMESPACE) svc/temporal-web 8080:8080
	@trap 'kill %1' EXIT

## load — run the load simulator locally (requires port-forward running)
load:
	python -m valet.load_simulator

## clean — tear down everything
clean:
	@echo "==> Deleting worker deployment..."
	-kubectl delete -f k8s/valet-worker.yaml
	-kubectl delete -f k8s/temporal-connection.yaml
	@echo "==> Uninstalling Worker Controller..."
	-helm uninstall temporal-worker-controller -n $(WORKER_CONTROLLER_NAMESPACE)
	-helm uninstall temporal-worker-controller-crds -n $(WORKER_CONTROLLER_NAMESPACE)
	-helm uninstall cert-manager -n cert-manager
	@echo "==> Deleting Temporal dev server..."
	-kubectl delete -f k8s/temporal-dev-server.yaml
	@echo "==> Deleting namespaces..."
	-kubectl delete namespace $(TEMPORAL_NAMESPACE)
	-kubectl delete namespace $(WORKER_CONTROLLER_NAMESPACE)
	-kubectl delete namespace cert-manager
	@echo "==> Stopping minikube..."
	minikube stop
	@echo "==> Clean complete."
