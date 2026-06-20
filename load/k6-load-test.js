// =============================================================================
// k6 load test — Forum Wędkarskie API (demo skalowania HPA na minikube).
//
// Profile (env PROFILE, default "demo") — dobrane pod maszynę 16 GB RAM
// z ~10 GB dla WSL/minikube:
//
//   smoke  — 1 VU / 30 s. Sanity check przed prezentacją (czy API żyje).
//   demo   — schodkowy ramp 10 → 40 → 80 VU (~7 min). Wyraźne plateau,
//            żeby na dashboardzie Grafany było widać HPA 1 → 2 → 3 repliki
//            i stabilizację latencji po doskalowaniu. NIE wysyca puli DB.
//   stress — ramp do 150 VU (~6,5 min). Weryfikacja fixu puli połączeń
//            (pool 10+10 per pod); spodziewany wzrost p95, ale bez kaskady
//            padających readiness probe'ów jak przy starym poolu 5+10.
//
// Uruchamianie: scripts/run-load-test.ps1 [-TestProfile demo|smoke|stress]
// Lokalnie:     k6 run -e BASE_URL=http://forum.local -e PROFILE=demo load/k6-load-test.js
//
// Ruch: wyłącznie publiczne GET-y, ważony mix imitujący realne przeglądanie
// forum. Celowo NIE odpytujemy /health/ready — to endpoint dla kubeleta;
// obciążanie go zaburza sygnał readiness podczas testu.
// =============================================================================
import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Counter } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://backend-service:8000";
const PROFILE = (__ENV.PROFILE || "demo").toLowerCase();

const errorRate = new Rate("errors");
const requests = new Counter("forum_requests");

// --- Profile obciążenia ------------------------------------------------------
// Schodki z plateau ≥ 90 s: HPA (stabilizationWindow scaleUp=30 s, metryki
// co 15 s) potrzebuje ~1 min, żeby zareagować i pokazać to na wykresie.
const PROFILES = {
  smoke: {
    stages: [{ duration: "30s", target: 1 }],
    thresholds: {
      http_req_duration: ["p(95)<800"],
      errors: ["rate<0.01"],
    },
  },
  demo: {
    stages: [
      { duration: "1m", target: 10 },   // baseline — 1 pod spokojnie wystarcza
      { duration: "30s", target: 40 },  // ramp — CPU > 70% requestu
      { duration: "2m", target: 40 },   // plateau — HPA dokłada 2. pod
      { duration: "30s", target: 80 },  // drugi schodek
      { duration: "2m", target: 80 },   // plateau — HPA dokłada 3. pod
      { duration: "1m", target: 0 },    // ramp down (scale-in po ~3 min — okno 180 s)
    ],
    thresholds: {
      http_req_duration: ["p(95)<1000"],
      errors: ["rate<0.02"],
    },
  },
  stress: {
    stages: [
      { duration: "30s", target: 50 },
      { duration: "1m", target: 50 },
      { duration: "30s", target: 100 },
      { duration: "1m", target: 100 },
      { duration: "30s", target: 150 },
      { duration: "2m", target: 150 },  // peak — tu padał stary pool 5+10
      { duration: "1m", target: 0 },
    ],
    thresholds: {
      // Informacyjne — stress ma pokazać granice, nie przerywać testu.
      http_req_duration: ["p(95)<2000"],
      errors: ["rate<0.05"],
    },
  },
};

const profile = PROFILES[PROFILE] || PROFILES.demo;

export const options = {
  scenarios: {
    browse: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: profile.stages,
      gracefulRampDown: "20s",
    },
  },
  thresholds: {
    ...profile.thresholds,
    // Submetryki per endpoint — dzięki temu trafiają do summary JSON
    // i do raportu HTML (progi celowo luźne, chodzi o rozbicie statystyk).
    "http_req_duration{endpoint:posts_list}": ["p(95)<3000"],
    "http_req_duration{endpoint:post_detail}": ["p(95)<3000"],
    "http_req_duration{endpoint:comments}": ["p(95)<3000"],
    "http_req_duration{endpoint:categories}": ["p(95)<3000"],
    "http_req_duration{endpoint:tags}": ["p(95)<3000"],
  },
  // "count" w statystykach trendów — raport HTML liczy z tego udział endpointów.
  summaryTrendStats: ["avg", "min", "med", "max", "p(90)", "p(95)", "count"],
  // Mniej pracy po stronie k6 (mały pod, limit 256 Mi RAM).
  discardResponseBodies: false,
};

// --- Setup: zbierz realne ID postów, żeby testować też widok szczegółów -----
export function setup() {
  const ids = [];
  const res = http.get(`${BASE_URL}/api/v1/posts?limit=20`);
  if (res.status === 200) {
    try {
      const body = res.json();
      const items = body.data?.items || body.items || body.data || [];
      for (const p of items) {
        if (p && p.public_id) ids.push(p.public_id);
      }
    } catch (_) {
      // brak danych — lecimy samymi listami
    }
  }
  return { postIds: ids };
}

// --- Ważony mix ruchu (suma wag = 100) ---------------------------------------
function pickAction(postIds) {
  const r = Math.random() * 100;
  if (r < 40) return { name: "posts_list", url: "/api/v1/posts?limit=20" };
  if (r < 65 && postIds.length > 0) {
    const id = postIds[Math.floor(Math.random() * postIds.length)];
    // 50/50: szczegół posta albo jego komentarze
    return Math.random() < 0.5
      ? { name: "post_detail", url: `/api/v1/posts/${id}` }
      : { name: "comments", url: `/api/v1/posts/${id}/comments` };
  }
  if (r < 85) return { name: "categories", url: "/api/v1/categories" };
  return { name: "tags", url: "/api/v1/tags" };
}

export default function (data) {
  const action = pickAction(data.postIds);
  const res = http.get(`${BASE_URL}${action.url}`, {
    tags: { endpoint: action.name },
  });
  requests.add(1, { endpoint: action.name });
  const ok = check(
    res,
    { "status 2xx/3xx": (r) => r.status >= 200 && r.status < 400 },
    { endpoint: action.name },
  );
  errorRate.add(!ok, { endpoint: action.name });
  // Think-time 0.3–0.7 s — realistyczniej niż stałe sleep i mniejsze piki RAM w k6.
  sleep(0.3 + Math.random() * 0.4);
}

// --- Podsumowanie: tekst na stdout + JSON dla generatora raportu HTML --------
// run-load-test.ps1 wycina blok między markerami i buduje load/results/report.html.
export function handleSummary(data) {
  const m = data.metrics;
  const fmt = (v, d = 1) => (v === undefined || v === null ? "-" : Number(v).toFixed(d));
  const dur = m.http_req_duration?.values || {};
  const reqs = m.http_reqs?.values || {};
  const errs = m.errors?.values || {};
  const checks = m.checks?.values || {};

  const lines = [
    "",
    "=== PODSUMOWANIE TESTU (" + PROFILE + ") ===",
    `requesty:   ${reqs.count || 0} (${fmt(reqs.rate)} req/s)`,
    `latencja:   avg=${fmt(dur.avg)}ms  p90=${fmt(dur["p(90)"])}ms  p95=${fmt(dur["p(95)"])}ms  max=${fmt(dur.max)}ms`,
    `błędy:      ${fmt((errs.rate || 0) * 100, 2)}%`,
    `checki OK:  ${checks.passes || 0} / ${(checks.passes || 0) + (checks.fails || 0)}`,
    "",
    "===K6_SUMMARY_JSON_BEGIN===",
    JSON.stringify({ profile: PROFILE, baseUrl: BASE_URL, metrics: data.metrics, state: data.state }),
    "===K6_SUMMARY_JSON_END===",
    "",
  ];
  return { stdout: lines.join("\n") };
}
