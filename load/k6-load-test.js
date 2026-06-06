// =============================================================================
// k6 load test for the Forum Wędkarskie API.
//
// Purpose: generate enough read traffic to (a) cross the backend HPA's 70% CPU
// target so you can watch it scale 2 -> 6 replicas, and (b) show traffic being
// load-balanced across pods (backend-service is a ClusterIP that round-robins).
//
// Run in-cluster (recommended, no local install) via scripts/run-load-test.ps1,
// or locally:
//   k6 run -e BASE_URL=http://forum.local load/k6-load-test.js
//
// All requests are unauthenticated GETs against public endpoints.
// =============================================================================
import http from "k6/http";
import { check, sleep } from "k6";
import { Rate } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://backend-service:8000";
const errorRate = new Rate("errors");

export const options = {
  scenarios: {
    ramp: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "30s", target: 30 },   // warm up
        { duration: "1m", target: 80 },     // ramp up — HPA should kick in here
        { duration: "2m", target: 80 },     // sustained load — watch replicas grow
        { duration: "1m", target: 150 },    // push harder
        { duration: "1m", target: 150 },    // hold at peak
        { duration: "1m", target: 0 },      // ramp down — watch it scale back in
      ],
      gracefulRampDown: "20s",
    },
  },
  thresholds: {
    // Informational: the test does NOT abort if these are breached — under
    // peak load some latency/errors are expected before the HPA catches up.
    http_req_duration: ["p(95)<1500"],
    errors: ["rate<0.05"],
  },
};

// Public read endpoints exercised by the test.
const endpoints = [
  "/health/ready",
  "/api/v1/categories",
  "/api/v1/posts?limit=20",
  "/api/v1/tags",
];

export default function () {
  for (const path of endpoints) {
    const res = http.get(`${BASE_URL}${path}`);
    const ok = check(res, {
      "status is 2xx/3xx": (r) => r.status >= 200 && r.status < 400,
    });
    errorRate.add(!ok);
  }
  sleep(0.5);
}
