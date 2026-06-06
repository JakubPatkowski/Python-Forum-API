# Kubernetes Troubleshooting — Minikube DevOps Best Practices

**Document Status:** v0.1 (2026-06-04)  
**Applies To:** Minikube + Docker Desktop + Windows + Ingress  
**Related:** docs/07 (audit), docs/14 (PowerShell best practices)

---

## TL;DR — Co Się Stało?

Ty zrobiłeś to w tej kolejności:

```
1. minikube tunnel (start) ← OK
2. kubectl apply ... (deploy) ← OK
3. test http://localhost:30080 ← FAIL
4. test http://forum.local ← FAIL
5. minikube delete (w trakcie tunelu!) ← BADDIE
6. minikube start ← nowy cluster
```

**Rezultat:** Split-brain Kubernetes:
- stary cluster z tunnel-lock
- nowy cluster bez svc/ingress
- Docker bridge zaraz po restart-u
- curl nie wie co jest źródłem prawdy

**Fix:** `.\scripts\reset-minikube.ps1 -NoPrompt`

---

## Dlaczego Nic Nie Działało?

### Problem 1: Tunnel Lock + Delete
```
minikube tunnel → .tunnel_lock istnieje
minikube delete → AH! proces tunelu trzyma lock
                 → delete FAILS (czściowo)
```

**Efekt:** Stary cluster "nie do końca usunięty", nowy cluster "nie do końca nowy".

### Problem 2: Ingress bez Backendu
```
kubectl get ingress -n forum-wedkarskie
→ NAME: forum-app
→ ADDRESS: 192.168.49.2
→ HOSTS: forum.local
```

Ale:
```
kubectl get svc -n forum-wedkarskie
→ backend-service: NONE (ClusterIP!)
→ no external routing
```

**Efekt:** DNS (`forum.local` → `192.168.49.2`) OK, ale ingress nie ma nikogo do routowania.

### Problem 3: Docker Bridge Po Restarcie
```
minikube start → nowy Docker container
Docker bridge zmienia się
Windows routing table: 192.168.49.x stary, nowy jest inny
```

**Efekt:** Nawet jeśli ingress by działał, Windows nie wie jak routować do `192.168.49.2`.

### Problem 4: localhost:30080 Nie Działał
```
NodePort: 30080
Ale: frontend-service = NodePort, ale pods nie było / nie były ready
```

**Efekt:** Port otwarty, ale nic nie słucha.

---

## Jak Kubernetes Propaguje Stan

```
┌─────────────────────────────────────────────────────────────┐
│ INGRESS RULE (spec.rules)                                   │
│   hosts: [forum.local]                                       │
│   backend: forum-app-svc:80                                  │
└────────────┬──────────────────────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────────────────────────┐
│ SERVICE (forum-app-svc)                                      │
│   selector: app: forum-app                                   │
│   port: 80 → targetPort: 3000                               │
└────────────┬──────────────────────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────────────────────────┐
│ POD (app: forum-app)                                         │
│   container: frontend:latest                                 │
│   port: 3000                                                 │
└─────────────────────────────────────────────────────────────┘
```

**Jeśli podział:**
- Ingress istnieje, Service NIE istnieje
  → Ingress kontroler szuka Service
  → Service nie ma endpoints
  → Ingress zwraca 503 Service Unavailable

- Service istnieje, Pod NIE istnieje
  → Service ma 0 endpoints
  → LoadBalancer / Ingress ma nic do routowania
  → Hangs lub timeout

---

## Best Practices dla Dev Setup Minikube

### ❌ NIGDY RÓB TEGO

```powershell
# Zły pattern 1: delete w trakcie tunelu
minikube tunnel &
minikube delete  # WILL FAIL (tunnel lock)

# Zły pattern 2: test portów bez svc ready
minikube start
kubectl apply ...
curl http://localhost:30080  # SVC może nie być ready!

# Zły pattern 3: inny cluster bez redeploya
minikube delete
minikube start
# ... ingress rules z poprzedniego cluster'a dalej w kubeconfig
```

### ✅ PRAWIDŁOWY FLOW

```powershell
# 1. CLEAN state (opcjonalnie)
.\scripts\reset-minikube.ps1 -NoPrompt

# 2. Deploy
.\scripts\deploy.ps1 -Build

# 3. POCZEKAJ na pods
kubectl wait --for=condition=ready pod \
  -l app=backend \
  -n forum-wedkarskie \
  --timeout=300s

# 4. Test localhost:NodePort (brak tunelu!)
curl http://localhost:30080

# 5. JEŚLI chcesz ingress, dopiero WTEDY tunnel
minikube tunnel
curl http://forum.local
```

### Kiedy Używać Tunnel vs NodePort

| Tryb | Use Case | Command | URL |
|------|----------|---------|-----|
| **NodePort** | Dev, brak ingress | - | `http://localhost:30080` |
| **Tunnel** | Ingress testing, DNS | `minikube tunnel` | `http://forum.local` |
| **Port-Forward** | Debug service | `kubectl port-forward svc/backend 8000:8000` | `http://localhost:8000` |

---

## Diagnostyka Krok Po Kroku

### 1. Czy Cluster Istnieje?

```powershell
minikube status
# Output: host: Running, kubelet: Running, apiserver: Running
```

### 2. Czy Ingress Jest Enabled?

```powershell
kubectl get pods -n ingress-nginx
# Powinno być: ingress-nginx-controller-* (Running)
```

### 3. Czy Ingress Ma Rules?

```powershell
kubectl get ingress -n forum-wedkarskie
# NAME        CLASS   HOSTS         ADDRESS        PORTS
# forum-app   nginx   forum.local   192.168.49.2   80
```

### 4. Czy Service Istnieje i Ma Endpoints?

```powershell
kubectl get svc -n forum-wedkarskie
# Powinno być: backend-service, frontend-service (ClusterIP/NodePort)

kubectl describe svc frontend-service -n forum-wedkarskie
# Endpoints: 10.244.0.x:80, 10.244.0.y:80 (musi być >= 1)
```

### 5. Czy Pods Działają?

```powershell
kubectl get pods -n forum-wedkarskie
# STATUS: Running (nie Pending, CrashLoopBackOff, ImagePullBackOff)

kubectl logs deployment/backend -n forum-wedkarskie
# Check for errors
```

### 6. DNS Windows

```powershell
ping forum.local
# Reply from 192.168.49.2 (lub localhost, zależy od setup)

ipconfig /displaydns
# Szukaj: forum.local → IP
```

### 7. Network Connectivity (Routing)

```powershell
route print
# Szukaj: 192.168.49.0/24 via Hyper-V / Docker adapter

# Jeśli brakuje, musisz tunnel:
minikube tunnel
```

### 8. Curl Test

```powershell
# NodePort (brak tunelu)
curl http://localhost:30080 -v

# Ingress (z tunnel)
curl http://forum.local -v

# Service via port-forward
kubectl port-forward svc/backend-service 8000:8000 -n forum-wedkarskie
curl http://localhost:8000/health -v
```

---

## Znane Problemy — Deep Dive

### Problem: Ingress ADDRESS = `<pending>`

```
kubectl get ingress
# ADDRESS = <pending>
```

**Przyczyny:**
1. Ingress controller nie jest ready
2. Load Balancer type (AWS/Azure), a Ty masz Minikube
3. RBAC permissions
4. Network plugin nie skonfigurowany

**Fix:**
```powershell
# Check controller
kubectl get pods -n ingress-nginx

# Check events
kubectl describe ingress forum-app -n forum-wedkarskie

# Restart controller
kubectl rollout restart deployment ingress-nginx-controller -n ingress-nginx
```

### Problem: curl localhost:30080 Returns Connection Refused

**Przyczyny:**
1. Pod nie jest ready
2. NodePort service nie ma endpoints
3. Port forward nie aktywny

**Diagnostyka:**
```powershell
# Czy pod istnieje?
kubectl get pods -n forum-wedkarskie

# Czy pod jest ready?
kubectl describe pod <pod-name> -n forum-wedkarskie

# Czy service ma endpoints?
kubectl get endpoints -n forum-wedkarskie

# Czy port jest otwarty?
netstat -ano | findstr :30080
```

### Problem: curl forum.local Returns Destination Net Unreachable

**Przyczyny:**
1. Tunnel nie aktywny
2. Windows routing nie ma 192.168.49.0/24
3. DNS OK, ale routing FAIL

**Fix:**
```powershell
# 1. Start tunnel
minikube tunnel

# 2. Czekaj
# NOTE: Please do not close this terminal as this process must stay alive for the tunnel to be accessible ...

# 3. W innym terminal
ping forum.local
curl http://forum.local
```

### Problem: minikube tunnel Says "Socket Address Already in Use"

**Przyczyny:**
1. Stary tunnel proces wciąż działał
2. Port 80 zajęty

**Fix:**
```powershell
# 1. Kill old tunnel
taskkill /F /IM minikube.exe

# 2. Remove lock
Remove-Item "$env:USERPROFILE\.minikube\profiles\minikube\.tunnel_lock" -Force

# 3. Restart
minikube tunnel
```

---

## Script: reset-minikube.ps1

**Lokalizacja:** `./scripts/reset-minikube.ps1`

**Co robi:**
1. Zabija wszystkie minikube/kubectl procesy
2. Usuwa tunnel lock
3. Usuwa stary cluster (`minikube delete --purge`)
4. Restartuje Docker Desktop (kluczowe dla networking)
5. Startuje nowy cluster (4 CPU, 8 GB RAM)
6. Enableuje ingress
7. Deployuje stack (jeśli `!-SkipDeploy`)
8. Czeka na pods ready
9. Robi summary (co działa)

**Użycie:**

```powershell
# Full reset + deploy
.\scripts\reset-minikube.ps1

# Full reset + deploy, bez pytań
.\scripts\reset-minikube.ps1 -NoPrompt

# Reset cluster only (bez deploy)
.\scripts\reset-minikube.ps1 -SkipDeploy

# Verbose output
.\scripts\reset-minikube.ps1 -Verbose
```

---

## Checklist — Zanim Raportujesz Bug'a

- [ ] `minikube status` = Running
- [ ] `kubectl get pods -n forum-wedkarskie` = all Running
- [ ] `kubectl get svc -n forum-wedkarskie` = all have ENDPOINTS >= 1
- [ ] `kubectl get ingress -n forum-wedkarskie` = ADDRESS not `<pending>`
- [ ] `curl http://localhost:30080` = 200 lub redirect
- [ ] `minikube tunnel` aktywny (nowy terminal)
- [ ] `curl http://forum.local` = 200 lub redirect
- [ ] `kubectl logs deployment/backend -n forum-wedkarskie` = no errors

Jeśli coś nie OK:
1. `kubectl describe <resource>` (pod/svc/ingress)
2. `kubectl logs` (deployment/backend, deployment/frontend)
3. `minikube logs` (cluster internals)

---

## TL;DR — Szybki Fix

```powershell
# Jeśli nic nie działa:
.\scripts\reset-minikube.ps1 -NoPrompt

# Czekaj ~3 minuty

# Test
curl http://localhost:30080
# lub
minikube tunnel
curl http://forum.local
```

---

## Linki

- [Minikube Ingress](https://minikube.sigs.k8s.io/docs/handbook/ingress/)
- [Kubernetes Services](https://kubernetes.io/docs/concepts/services-networking/service/)
- [Docker Desktop Networking](https://docs.docker.com/desktop/networking/)
- docs/07 — Kubernetes hardening & monitoring
- docs/14 — PowerShell best practices
