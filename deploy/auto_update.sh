#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/home/assistea/AssisTea-Backend-Server"
VENV_PIP="$REPO_DIR/venv/bin/pip"
LOG_FILE="/home/assistea/cron.log"
BRANCH="${BRANCH:-dev}"
RECIPIENTS="${RECIPIENTS:-}"

log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') : $*" >> "$LOG_FILE"
}

cd "$REPO_DIR" || {
  log "ERROR: cannot cd to $REPO_DIR"
  exit 1
}

log "Checking for updates on branch '$BRANCH'"

git fetch --prune origin "$BRANCH" >> "$LOG_FILE" 2>&1

LOCAL_HASH="$(git rev-parse HEAD)"
REMOTE_HASH="$(git rev-parse "origin/$BRANCH")"

if [[ "$LOCAL_HASH" != "$REMOTE_HASH" ]]; then
  log "New commit detected. Pulling changes..."

  git pull --ff-only origin "$BRANCH" >> "$LOG_FILE" 2>&1

  log "Installing/updating requirements..."
  "$VENV_PIP" install -r "$REPO_DIR/requirements.txt" >> "$LOG_FILE" 2>&1
  log "Requirements updated."

  COMMIT_INFO="$(git log -1 --pretty=format:'Author: %an%nDate: %ad%nMessage: %s')"

  if [[ -n "$RECIPIENTS" ]] && command -v msmtp >/dev/null 2>&1 && [[ -f "$HOME/.msmtprc" ]]; then
    {
      echo "Subject: AssisTea server updated"
      echo
      echo "Server updated due to a new commit on branch '$BRANCH'."
      echo
      echo "$COMMIT_INFO"
    } | msmtp $RECIPIENTS >> "$LOG_FILE" 2>&1 || log "WARNING: email notification failed"
  else
    log "Email skipped (set RECIPIENTS + ~/.msmtprc + msmtp to enable)."
  fi
else
  log "No new commit."
fi
