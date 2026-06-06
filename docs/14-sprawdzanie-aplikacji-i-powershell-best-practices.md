# 14 — Sprawdzanie aplikacji po deployu i best practices PowerShella

> **Cel dokumentu:** instrukcja jak sprawdzić, że deploy się powiódł, oraz
> przewodnik po błędach PowerShella, by nie powtarzać się w przyszłości.
>
> **Data:** 2026-06-04 · **Autor:** Claude (sesja dedykowana fixom scriptów)

---

## 1. Sprawdzenie aplikacji po deployu

Po uruchomieniu `.\scripts\deploy.ps1 -Build -Monitoring` powinieneś zobaczyć:

```
  Deploy complete!
========================================
  Dodaj tę linię do C:\Windows\System32\drivers\etc\hosts (jako Administrator):
    <minikube-ip>   forum.local
```

### 1.1. Dodaj wpis do hosts

Otwórz **Notatnik jako Administrator** i edytuj plik:
```
C:\Windows\System32\drivers\etc\hosts
```

Dodaj na końcu (zamień `<minikube-ip>` na IP z komunikatu, np. `192.168.49.2`):
```
192.168.49.2   forum.local
```

Zapisz i zamknij.

### 1.2. Przegląd aplikacji

Otwórz przeglądarkę i przejdź do:

**Frontend (aplikacja forum):**
```
http://forum.local
```

Powinieneś zobaczyć listę kategorii, logowanie, rejestrację i listę postów.

**Swagger (dokumentacja API):**
```
http://forum.local/docs
```

Tutaj możesz testować endpointy API bezpośrednio. Zaloguj się i próbuj:
- POST `/api/v1/auth/register` — rejestracja
- POST `/api/v1/auth/login` — logowanie
- GET `/api/v1/posts` — lista postów

**MinIO konsola (obiekty S3):**
```
http://<minikube-ip>:30901
```
Login: `minioadmin` / `minioadmin`

Powinieneś zobaczyć bucket `uploads`.

### 1.3. Monitoring (opcjonalnie, jeśli deploy był z `-Monitoring`)

W nowym oknie PowerShella uruchom:
```powershell
.\scripts\portforward.ps1
```

Powinieneś zobaczyć listy port-forwardów:
```
  Backend/Swagger  -> http://localhost:8000
  Frontend         -> http://localhost:3000
  PostgreSQL       -> localhost:5432
  MinIO console    -> http://localhost:9001
  Grafana          -> http://localhost:3001
  Prometheus       -> http://localhost:9090
```

Otwórz **Grafana:**
```
http://localhost:3001
```
Login: `admin` / `admin`

Przejdź do **Dashboards** → **Forum Overview** — powinieneś zobaczyć:
- CPU/pamięć backendu
- Liczbę requestów
- Logi z ostatnich minut

### 1.4. Test autoskalowania

W trzecim oknie PowerShella:
```powershell
.\scripts\run-load-test.ps1 -Watch
```

Powinieneś zobaczyć:
1. Test k6 się uruchamia i generuje ruch
2. W oknie Grafany (lub watch HPA):
   ```
   kubectl get hpa backend -n forum-wedkarskie -w
   ```
   Repliki backendu powinny wzrosnąć z 2 do maksymalnie 6 pod obciążeniem

### 1.5. Sprawdzenie logu backendu

Obejrzyj logi ostatnich deployów:
```powershell
kubectl logs deployment/backend -n forum-wedkarskie --tail=50
```

Powinieneś zobaczyć:
```
INFO: Uvicorn running on http://0.0.0.0:8000
INFO: Application startup complete
```

---

## 2. PowerShell — best practices by uniknąć błędów

### Pułapka #1: `$ErrorActionPreference = "Stop"` + non-zero exit code

**Problem:**
```powershell
$ErrorActionPreference = "Stop"
kubectl get secret foo -n bar *> $null   # powinno ignorować błąd
# Ale PowerShell ZAWSZE zatrzyma się, bo `kubectl` zwróci exit code 1
```

**Rozwiązanie:**
Wyłącz krotko `$ErrorActionPreference` dla polecenia, które może failować:

```powershell
$ErrorActionPreference = "SilentlyContinue"
kubectl get secret foo -n bar -o name 2>$null | Out-Null
$ErrorActionPreference = "Stop"
if ($LASTEXITCODE -eq 0) { 
    # coś istnieje
}
```

Lub użyj `try { } catch { }`:
```powershell
try {
    kubectl wait --for=condition=complete job/foo -n bar --timeout=180s
} catch {
    Write-Host "Job nie ukończył się!" -ForegroundColor Red
    throw
}
```

### Pułapka #2: Znaki specjalne w string'ach (em-dash, cudzysłów)

**Problem:**
```powershell
Write-Host "Starting minikube (4 CPU / 8GB)..." -ForegroundColor Gray
# PowerShell widzi `/` i myśli, że to koniec wyrażenia
# Błąd: "Missing closing ')' in expression"
```

**Rozwiązanie:**
- Unikaj `em-dash` (—) — używaj `-` lub ` - `
- Unikaj `fancy cudzysłowów` („" / "") — tylko `"` lub `'`
- Unikaj `fancy apostrofów` (') — tylko `'` lub `'`

```powershell
# DOBRY kod:
Write-Host "Starting minikube (4 CPU, 8GB)..." -ForegroundColor Gray
Write-Host "OK - migrations applied" -ForegroundColor Green
Write-Host "Please add this line..." -ForegroundColor White
```

### Pułapka #3: Cudzysłów w parametrach cmdlet'ów

**Problem:**
```powershell
Write-Host "Add this to C:\Windows\System32\drivers\etc\hosts (as Administrator):" -ForegroundColor White
# Jeśli skopujesz z Worda/dokumentu, cudzysłów może być `"` zamiast `"`
# PowerShell nie pozna tego jako operator
```

**Rozwiązanie:**
Zawsze pisz skrypty w edytorze, który obsługuje zwykły ASCII:
- **VS Code** (domyślnie ASCII)
- **Notepad** (Windows)
- **PowerShell ISE** (preferowany do testów)

NIE używaj:
- Word
- Google Docs
- Notatki (ze smartquotes)
- iCloud Notes

### Pułapka #4: Przekierowania i null `*>` vs `2>`

**Problem:**
```powershell
kubectl get foo *> $null  # NIE działa solidnie wszędzie
```

**Rozwiązanie:**
```powershell
# Do stdout i stderr:
kubectl get foo 2>$null | Out-Null

# Lub bezpieczniej z try/catch:
try {
    kubectl get foo -o name 2>$null | Out-Null
} catch {
    # brak zasobu — ignoruj
}
```

### Pułapka #5: Kodowanie pliku (BOM vs UTF-8)

**Problem:**
Jeśli plik ma UTF-8 z BOM, PowerShell może się pogubić ze znakami specjalnymi
(choć polskie znaki to już problem):

```powershell
Write-Host "Forum Wędkarskie" # Może nie wypisać prawidłowo
```

**Rozwiązanie:**
Zapisz skrypty zawsze jako **UTF-8 bez BOM**:
- **VS Code:** dolny prawy róg → `UTF-8` (bez BOM zaznaczenia)
- Albo w PowerShell:

```powershell
# Zapisz plik UTF-8 bez BOM
$content = Get-Content "plik.ps1" -Raw
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText("plik.ps1", $content, $utf8NoBom)
```

---

## 3. Konwencje dla skryptów w tym projekcie

Obowiązują od teraz dla wszystkich nowych/edytowanych skryptów `.ps1`:

| Reguła | Czemu | Przykład |
|--------|-------|---------|
| Brak em-dashy (—), tylko `-` lub ` - ` | PowerShell myli się w wyrażeniach | ✅ `Waiting - 5s` ❌ `Waiting — 5s` |
| Brak fancy cudzysłowów („"), tylko ASCII `"` lub `'` | Parser nie rozpozna | ✅ `"hello"` ❌ `"hello"` |
| Unikaj polskich znaków w string'ach (UTF-8 w komentarzach OK) | Mogą się nie wypisać czy pogubić przy redirekcji | ✅ `# Forum forum` w komentarzu ✅ `Write-Host "app started"` |
| `$ErrorActionPreference = "SilentlyContinue"` + `$LASTEXITCODE` dla komend, które mogą failować | Bezpieczna obsługa błędów bez przerywania | patrz pułapka #1 |
| Zawsze `$ErrorActionPreference = "Stop"` na początku skryptu | Fail-fast na nieoczekiwane błędy | Linia 2 każdego skryptu |
| Komentarze przed sekcją zamiast `# ----` | Czytelność; kreski mogą mieć problemy ze znakami | ✅ `# 1. minikube up` ❌ `# ───────────────` |
| Zapisz plik jako UTF-8 bez BOM | Kompatybilność | Settings → UTF-8 (bez zaznaczenia BOM) |

---

## 4. Testy na sobie przed pushowaniem

Jeśli edytujesz skrypt PowerShella:

1. **Sprawdzenie składni** (bez uruchamiania):
   ```powershell
   Test-Path ".\scripts\deploy.ps1"
   $ast = [System.Management.Automation.Language.Parser]::ParseFile(
       ".\scripts\deploy.ps1", [ref]$null, [ref]$null
   )
   $ast.Errors  # jeśli puste = OK
   ```

2. **Sucha próba** (`-WhatIf` jeśli dostępne):
   ```powershell
   # Niektóre cmdlety mają -WhatIf:
   kubectl apply -f file.yaml --dry-run=client
   ```

3. **Segment po segmencie**:
   Zamiast całego skryptu, kopiuj wiersze do PowerShella i testuj:
   ```powershell
   $status = minikube status --format "{{.Host}}" 2>$null
   if ($status -ne "Running") { Write-Host "Not running" }
   ```

---

## 5. Szybki troubleshooting

| Błąd | Przyczyna | Rozwiązanie |
|------|-----------|------------|
| `Unexpected token 'CPU' in expression` | Fancy znaki lub `/` w string'u | Zamień `"4 CPU / 8GB"` na `"4 CPU, 8GB"` |
| `Error from server (NotFound): secrets "foo" not found` + script zatrzymany | `$ErrorActionPreference = "Stop"` + non-zero exit | Dodaj `$ErrorActionPreference = "SilentlyContinue"` przed poleceniem |
| `The string is missing the terminator: "` | Cudzysłów z Word/Docs zamiast ASCII | Otwórz w VS Code i reedytuj string |
| Pod nigdy nie startuje, logi `CrashLoopBackOff` | ConfigMap/Secret brakuje | Sprawdź `kubectl describe pod <pod-name>` |
| Ingress pokazuje IP zamiast `forum.local` | Brakuje wpisu w `/etc/hosts` | Dodaj linię z IP minikube i `forum.local` |
| Frontend się nie łączy z API | CORS problem lub błędny `baseURL` | Sprawdź Network tab w DevTools, zobacz rzeczywisty request |

---

## 6. Podsumowanie — workflow do zapamięci

```
1. Edytuj skrypt w VS Code (UTF-8, bez BOM, ASCII-only znaki specjalne)
2. Testuj wiersze w PowerShell repl
3. Uruchom `.\scripts\deploy.ps1 -Build -Monitoring`
4. Poczekaj na `Deploy complete!`
5. Dodaj wpis do hosts
6. Otwórz http://forum.local
7. Jeśli coś nie działa: `kubectl logs`, `kubectl describe pod`
8. Fixuj, push, koniec
```

**Ostatni krok:** zawsze po deployu sprawdź:
```powershell
kubectl get pods -n forum-wedkarskie          # czy wszystkie running
kubectl get svc -n forum-wedkarskie           # czy service ma ClusterIP
curl http://forum.local 2>/dev/null | head -5 # czy frontend żyje
```

Powodzenia! 🚀
