#!/usr/bin/env bash
# Start a local Warden lab for a ladder run, on http://127.0.0.1:8000.
#
# It uses warden/backend/.env for the OpenAI key and the per-gate models,
# and overrides everything a bench run must not touch. python-dotenv never
# replaces a variable that is already set, so the values below win over
# the file:
#   - throwaway passwords, so run logs never hold the production ones
#   - a throwaway CERT_SECRET, which turns gate-order enforcement on
#   - no Worker gate auth, no Slack win alerts, no writes to the Supabase corpus
#   - a higher submit limit, because TAP retries candidate variants
#
#   operator/ladder/local-lab.sh            # leave it running, then start the ladder in another terminal
#   WARDEN_REPO=/path/to/warden operator/ladder/local-lab.sh
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
repo="${WARDEN_REPO:-$(cd "$here/../../../warden" 2>/dev/null && pwd)}"
lab="$repo/backend"
[[ -f "$lab/app/main.py" ]] || { echo "lab not found at $lab (set WARDEN_REPO)" >&2; exit 1; }
[[ -f "$lab/.env" ]] || { echo "no $lab/.env (it needs OPENAI_API_KEY and the MODEL_n lines)" >&2; exit 1; }

# Random throwaway passwords. Gate 8 gets two words joined by an underscore.
words=(LANTERN COPPER ORCHARD THIMBLE GRANITE MEADOW HARBOR CINDER QUARRY
       BRAMBLE SPINDLE MARIGOLD TUNDRA PEWTER WALNUT LAGOON FATHOM JUNIPER)
mapfile -t pick < <(printf '%s\n' "${words[@]}" | shuf -n 9)
for n in 1 2 3 4 5 6 7; do export "PASSWORD_$n=${pick[$((n-1))]}"; done
export PASSWORD_8="${pick[7]}_${pick[8]}"
CERT_SECRET="$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
export CERT_SECRET

# Keep the generated mapping observable without committing it. The private env
# file is for the lab operator; the JSON manifest gives the benchmark a stable
# run identity and password fingerprint without revealing any target value.
umask 077
run_id="$(date -u +%Y%m%dT%H%M%SZ)-local-$(head -c 4 /dev/urandom | od -An -tx1 | tr -d ' \n')"
private_env="$here/runs/local-lab.env"
public_manifest="$here/runs/local-lab.json"
mkdir -p "$here/runs"
{
  printf 'LAB_RUN_ID=%s\n' "$run_id"
  for n in 1 2 3 4 5 6 7 8; do
    name="PASSWORD_$n"
    printf '%s=%s\n' "$name" "${!name}"
  done
} > "$private_env"
password_fingerprint="$(printf '%s\n' "$PASSWORD_1" "$PASSWORD_2" "$PASSWORD_3" "$PASSWORD_4" \
  "$PASSWORD_5" "$PASSWORD_6" "$PASSWORD_7" "$PASSWORD_8" | sha256sum | cut -d' ' -f1)"
printf '{"lab_run_id":"%s","password_fingerprint":"%s"}\n' \
  "$run_id" "$password_fingerprint" > "$public_manifest"
chmod 600 "$private_env" "$public_manifest"

export GATE_AUTH_SECRET="" SLACK_BOT_TOKEN="" SLACK_CHANNEL=""
export CORPUS_LOG=off SUPABASE_URL="" SUPABASE_SERVICE_KEY=""
export SUBMIT_RATE_LIMIT="${SUBMIT_RATE_LIMIT:-120/minute}"

uvicorn="$lab/.venv/bin/uvicorn"
[[ -x "$uvicorn" ]] || uvicorn="uvicorn"
echo "local lab: http://127.0.0.1:8000  (throwaway passwords and CERT_SECRET; Slack and corpus off)"
echo "targets:   $private_env  (private, gitignored, mode 0600)"
cd "$lab" && exec "$uvicorn" app.main:app --host 127.0.0.1 --port 8000 --no-access-log
