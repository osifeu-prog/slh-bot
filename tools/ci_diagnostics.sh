#!/usr/bin/env bash
set -u

mkdir -p ci-diagnostics

{
  echo "=== SLH CI DIAGNOSTICS ==="
  date -u +"timestamp=%Y-%m-%dT%H:%M:%SZ"
  echo "workflow=${GITHUB_WORKFLOW:-unknown}"
  echo "job=${GITHUB_JOB:-unknown}"
  echo "event=${GITHUB_EVENT_NAME:-unknown}"
  echo "ref=${GITHUB_REF:-unknown}"
  echo "sha=${GITHUB_SHA:-unknown}"
  echo "run_id=${GITHUB_RUN_ID:-unknown}"
  echo "run_attempt=${GITHUB_RUN_ATTEMPT:-unknown}"
  echo "runner_name=${RUNNER_NAME:-unknown}"
  echo "runner_os=${RUNNER_OS:-unknown}"
  echo "runner_arch=${RUNNER_ARCH:-unknown}"
  echo "runner_environment=${RUNNER_ENVIRONMENT:-unknown}"
  echo
  echo "--- TOOLCHAIN ---"
  python --version 2>&1 || true
  python3 --version 2>&1 || true
  node --version 2>&1 || true
  npm --version 2>&1 || true
  git --version 2>&1 || true
  echo
  echo "--- GIT ---"
  git rev-parse --show-toplevel 2>&1 || true
  git rev-parse HEAD 2>&1 || true
  git status --short 2>&1 || true
} 2>&1 | tee ci-diagnostics/environment.txt

echo "diagnostics_captured=true" > ci-diagnostics/status.txt
