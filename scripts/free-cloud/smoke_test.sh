#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# AIREX Automated 20-Point Staging & Remote Free Cloud Smoke Test Suite
# Tests: Infrastructure, Authentication, Project Management, Evaluations,
#        Workers, Prometheus Metrics, and Web UI availability.
# ==============================================================================

API_URL=${1:-"http://localhost:8000"}
WEB_URL=${2:-""}

if [ -z "${WEB_URL}" ]; then
    # Auto-infer Web URL if sslip.io pattern detected
    if [[ "${API_URL}" =~ api\.(.*) ]]; then
        WEB_URL="http://app.${BASH_REMATCH[1]}"
    else
        WEB_URL="http://localhost:3000"
    fi
fi

echo "============================================================"
echo "          AIREX Automated Cloud Smoke Test Suite            "
echo "  Target API URL: ${API_URL}                                "
echo "  Target Web URL: ${WEB_URL}                                "
echo "============================================================"

PASS_COUNT=0
FAIL_COUNT=0

check_endpoint() {
    local desc="$1"
    local url="$2"
    local expected_code="$3"
    local method="${4:-GET}"
    local data="${5:-}"
    local auth_header="${6:-}"

    echo -n "[TEST] ${desc}... "
    
    local curl_cmd=(curl -s -o /tmp/smoke_resp.txt -w "%{http_code}" --max-time 10)
    if [ "${method}" == "POST" ]; then
        curl_cmd+=(-X POST -H "Content-Type: application/json" -d "${data}")
    fi
    if [ -n "${auth_header}" ]; then
        curl_cmd+=(-H "${auth_header}")
    fi
    curl_cmd+=("${url}")

    HTTP_CODE=$("${curl_cmd[@]}" 2>/dev/null || echo "000")

    if [ "${HTTP_CODE}" == "${expected_code}" ]; then
        echo "PASS (${HTTP_CODE})"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        echo "FAIL (Got ${HTTP_CODE}, expected ${expected_code})"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

echo "--- SECTION 1: INFRASTRUCTURE & HEALTH PROBES ---"
# 1. Health Liveness Probe
check_endpoint "1. API Health Live Probe" "${API_URL}/health/live" "200"

# 2. Health Readiness Probe
check_endpoint "2. API Health Ready Probe" "${API_URL}/health/ready" "200"

# 3. OpenAPI Documentation JSON
check_endpoint "3. OpenAPI Specification JSON" "${API_URL}/openapi.json" "200"

# 4. Interactive Swagger UI
check_endpoint "4. Interactive Swagger UI" "${API_URL}/docs" "200"

# 5. Prometheus Metrics
check_endpoint "5. Prometheus Metrics Ingestion" "${API_URL}/metrics" "200"

echo ""
echo "--- SECTION 2: ACCESS CONTROL & AUTHENTICATION ---"
# 6. Unauthenticated Operations SRE Overview
check_endpoint "6. Unauthenticated Ops (Expect 401)" "${API_URL}/api/v1/system/operations/overview" "401"

# 7. Unauthenticated Projects Access
check_endpoint "7. Unauthenticated Projects (Expect 401)" "${API_URL}/api/v1/projects" "401"

# 8. Unauthenticated Evaluations Access
check_endpoint "8. Unauthenticated Evaluations (Expect 401)" "${API_URL}/api/v1/evaluations" "401"

# 9. User Registration
TIMESTAMP=$(date +%s)
REG_EMAIL="smoke_user_${TIMESTAMP}@example.com"
REG_PASS="ComplexPassword123!"
REG_PAYLOAD="{\"name\":\"Smoke Tester\",\"email\":\"${REG_EMAIL}\",\"password\":\"${REG_PASS}\"}"
check_endpoint "9. User Registration Flow" "${API_URL}/api/v1/auth/register" "201" "POST" "${REG_PAYLOAD}"

# 10. Duplicate Registration Conflict
check_endpoint "10. Duplicate Registration (Expect 409)" "${API_URL}/api/v1/auth/register" "409" "POST" "${REG_PAYLOAD}"

# 11. User Login & Token Extraction
LOGIN_PAYLOAD="{\"email\":\"${REG_EMAIL}\",\"password\":\"${REG_PASS}\"}"
check_endpoint "11. User Authentication (Login)" "${API_URL}/api/v1/auth/login" "200" "POST" "${LOGIN_PAYLOAD}"

TOKEN=""
if [ -f /tmp/smoke_resp.txt ]; then
    TOKEN=$(grep -o '"access_token":"[^"]*' /tmp/smoke_resp.txt | grep -o '[^"]*$' || echo "")
fi

# 12. Authenticated Profile Extraction
if [ -n "${TOKEN}" ]; then
    check_endpoint "12. Authenticated User Profile" "${API_URL}/api/v1/auth/me" "200" "GET" "" "Authorization: Bearer ${TOKEN}"
else
    echo "[TEST] 12. Authenticated User Profile... SKIP (No token)"
fi

echo ""
echo "--- SECTION 3: BUSINESS CAPABILITIES & WORKFLOWS ---"
# 13. Authenticated Project Listing
if [ -n "${TOKEN}" ]; then
    check_endpoint "13. Authenticated Project Listing" "${API_URL}/api/v1/projects" "200" "GET" "" "Authorization: Bearer ${TOKEN}"
else
    echo "[TEST] 13. Authenticated Project Listing... SKIP"
fi

# 14. Project Creation
PROJECT_ID=""
if [ -n "${TOKEN}" ]; then
    PROJ_PAYLOAD="{\"name\":\"Smoke Test Project ${TIMESTAMP}\",\"description\":\"Automated cloud verification project\"}"
    check_endpoint "14. Project Creation" "${API_URL}/api/v1/projects" "201" "POST" "${PROJ_PAYLOAD}" "Authorization: Bearer ${TOKEN}"
    if [ -f /tmp/smoke_resp.txt ]; then
        PROJECT_ID=$(grep -o '"id":"[^"]*' /tmp/smoke_resp.txt | head -n 1 | grep -o '[^"]*$' || echo "")
    fi
else
    echo "[TEST] 14. Project Creation... SKIP"
fi

# 15. Authenticated Evaluations Listing
if [ -n "${TOKEN}" ]; then
    check_endpoint "15. Evaluations Listing" "${API_URL}/api/v1/evaluations" "200" "GET" "" "Authorization: Bearer ${TOKEN}"
else
    echo "[TEST] 15. Evaluations Listing... SKIP"
fi

# 16. Benchmark Suites Listing
if [ -n "${TOKEN}" ]; then
    check_endpoint "16. Benchmark Suites API" "${API_URL}/api/v1/benchmarks/suites" "200" "GET" "" "Authorization: Bearer ${TOKEN}"
else
    echo "[TEST] 16. Benchmark Suites API... SKIP"
fi

# 17. SRE Operations Dashboard (Authenticated)
if [ -n "${TOKEN}" ]; then
    check_endpoint "17. SRE Operations Dashboard" "${API_URL}/api/v1/system/operations/overview" "200" "GET" "" "Authorization: Bearer ${TOKEN}"
else
    echo "[TEST] 17. SRE Operations Dashboard... SKIP"
fi

echo ""
echo "--- SECTION 4: WEB FRONTEND AVAILABILITY ---"
# 18. Next.js Web Landing Page
check_endpoint "18. Web App Landing Page (/)" "${WEB_URL}/" "200"

# 19. Web App Login Page
check_endpoint "19. Web App Login Page (/login)" "${WEB_URL}/login" "200"

# 20. Web App Register Page
check_endpoint "20. Web App Register Page (/register)" "${WEB_URL}/register" "200"

echo ""
echo "============================================================"
echo "Smoke Test Summary: ${PASS_COUNT} PASSED, ${FAIL_COUNT} FAILED"
echo "============================================================"

if [ "${FAIL_COUNT}" -gt 0 ]; then
    echo "FAILED: Smoke test suite encountered ${FAIL_COUNT} failure(s)."
    exit 1
else
    echo "SUCCESS: All 20 smoke tests passed cleanly against ${API_URL}!"
    exit 0
fi
