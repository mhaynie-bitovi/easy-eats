TAG ?= latest
IMAGE_NAME = valet-worker
TEMPORAL_NAMESPACE = temporal
WORKER_CONTROLLER_NAMESPACE = temporal-worker-controller

.PHONY: setup build deploy status logs port-forward load clean

## setup — start minikube, deploy Temporal Server, install Worker Controller
setup:
	@echo "==> Starting minikube..."
	minikube start --cpus=4 --memory=8192
	@echo "==> Adding Helm repos..."
	helm repo add temporal https://temporalio.github.io/helm-charts
	helm repo add temporal-worker-controller https://temporalio.github.io/worker-controller
	helm repo update
	@echo "==> Creating temporal namespace..."
	kubectl create namespace $(TEMPORAL_NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -
	@echo "==> Installing Temporal Server..."
	helm upgrade --install temporal temporal/temporal \
		--namespace $(TEMPORAL_NAMESPACE) \
		-f k8s/temporal-server-values.yaml \
		--timeout 10m \
		--wait
	@echo "==> Installing Worker Controller..."
	kubectl create namespace $(WORKER_CONTROLLER_NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -
	helm upgrade --install temporal-worker-controller temporal-worker-controller/temporal-worker-controller \
		--namespace $(WORKER_CONTROLLER_NAMESPACE) \
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
	@echo "==> Uninstalling Temporal Server..."
	-helm uninstall temporal -n $(TEMPORAL_NAMESPACE)
	@echo "==> Deleting namespaces..."
	-kubectl delete namespace $(TEMPORAL_NAMESPACE)
	-kubectl delete namespace $(WORKER_CONTROLLER_NAMESPACE)
	@echo "==> Stopping minikube..."
	minikube stop
	@echo "==> Clean complete."
