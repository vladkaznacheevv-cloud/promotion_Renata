#!/usr/bin/env sh
set -eu

BASE="${BASE:-http://127.0.0.1}"
TMP_DIR="${TMPDIR:-/tmp}/renata_nginx_header_check.$$"
mkdir -p "$TMP_DIR"
trap 'rm -rf "$TMP_DIR"' EXIT INT TERM

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

request_check() {
  name="$1"
  host="$2"
  path="$3"
  expected_vhost="$4"
  expect_code="$5"   # exact code or "not_5xx"
  expect_json="$6"   # yes/no

  headers="$TMP_DIR/${name}.headers"
  body="$TMP_DIR/${name}.body"
  code="$(curl -sS -D "$headers" -o "$body" -H "Host: $host" "$BASE$path" -w "%{http_code}" || true)"
  server_hdr="$(grep -i '^Server:' "$headers" | tail -n1 | tr -d '\r' | cut -d' ' -f2- || true)"
  vhost_hdr="$(grep -i '^X-Renata-VHost:' "$headers" | tail -n1 | tr -d '\r' | cut -d' ' -f2- || true)"
  ctype_hdr="$(grep -i '^Content-Type:' "$headers" | tail -n1 | tr -d '\r' | cut -d' ' -f2- || true)"

  printf "%s: code=%s server=%s x-renata-vhost=%s\n" "$name" "$code" "${server_hdr:-<none>}" "${vhost_hdr:-<none>}"

  [ "$vhost_hdr" = "$expected_vhost" ] || fail "$name: expected X-Renata-VHost=$expected_vhost, got ${vhost_hdr:-<none>}"

  if [ "$expect_code" = "not_5xx" ]; then
    case "$code" in
      5*) fail "$name: unexpected 5xx ($code)" ;;
    esac
  else
    [ "$code" = "$expect_code" ] || fail "$name: expected HTTP $expect_code, got $code"
  fi

  if [ "$expect_json" = "yes" ]; then
    echo "$ctype_hdr" | grep -qi "application/json" || fail "$name: expected JSON content-type, got ${ctype_hdr:-<none>}"
  fi
}

echo "BASE=$BASE"

request_check "crm_root" "crm.<domain>" "/" "crm" "200" "no"
request_check "crm_api_auth_me" "crm.<domain>" "/api/auth/me" "crm" "401" "yes"
request_check "api_healthz" "api.<domain>" "/healthz" "api" "200" "yes"
request_check "api_api_root" "api.<domain>" "/api/" "api" "not_5xx" "no"

echo "OK: vhost routing looks correct"
