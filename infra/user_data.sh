#!/bin/bash
# =============================================================================
# Football League MS — EC2 first-boot setup script
#
# This script is injected into the EC2 instance as "User Data" by CDK.
# It runs ONCE as root when the instance first boots.
#
# Variables at the top are set by the CDK stack before this script runs:
#   APP_DIR, REPO_URL, DB_HOST, DB_PORT, DB_NAME, DB_USER, SECRET_ARN
# =============================================================================
set -euxo pipefail
exec > >(tee /var/log/user-data.log | logger -t user-data) 2>&1

# =============================================================================
# 1. System packages
# =============================================================================
dnf update -y
dnf install -y python3.11 python3.11-pip git nginx

# Make python3.11 available as 'python3' for convenience
alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# =============================================================================
# 2. Clone application repo
# =============================================================================
git clone "${REPO_URL}" "${APP_DIR}"
cd "${APP_DIR}"

# Always deploy from the main branch — merge your feature branches before deploying
git checkout main

# =============================================================================
# 3. Python virtual environment and dependencies
# =============================================================================
python3.11 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# =============================================================================
# 4. Fetch RDS credentials from AWS Secrets Manager
#
# WHY NOT STORE THE PASSWORD IN GIT:
#   Secrets in git are permanent. Even if you delete the file later, the
#   password exists in the git history forever. Anyone who ever clones the
#   repo — now or in the future — can find it. AWS Secrets Manager stores the
#   secret encrypted at rest, access is controlled by IAM, and the EC2
#   instance role is the only identity that can read it.
# =============================================================================
DB_SECRET_JSON=$(
  aws secretsmanager get-secret-value \
    --secret-id "${SECRET_ARN}" \
    --query SecretString \
    --output text
)

DB_PASSWORD=$(python3.11 -c "import sys, json; print(json.loads('${DB_SECRET_JSON}')['password'])")

# =============================================================================
# 5. Create .env file
#
# WHY .env NEVER GOES IN GIT:
#   - DATABASE_URL contains credentials (host, user, password)
#   - SECRET_KEY is used to sign JWTs — if leaked, anyone can forge auth tokens
#   - .env is in .gitignore; .env.example (no real values) IS committed as a
#     template so developers know what variables are required
# =============================================================================
cat > "${APP_DIR}/.env" << EOF
DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}
SECRET_KEY=$(python3.11 -c "import secrets; print(secrets.token_hex(32))")
EOF
chmod 600 "${APP_DIR}/.env"   # readable only by owner (root at this point)

# =============================================================================
# 6. Run Alembic migrations
#
# This creates all tables in the RDS PostgreSQL instance. We retry a few times
# because RDS may still be initialising even though CloudFormation marked it
# CREATE_COMPLETE.
# =============================================================================
export DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

for attempt in 1 2 3 4 5; do
  echo "Migration attempt ${attempt}/5..."
  if .venv/bin/alembic upgrade head; then
    echo "Migrations applied successfully."
    break
  fi
  if [ "${attempt}" -eq 5 ]; then
    echo "ERROR: migrations failed after 5 attempts." >&2
    exit 1
  fi
  sleep 15
done

# =============================================================================
# 7. Gunicorn as a systemd service
#
# WHY GUNICORN INSTEAD OF UVICORN DIRECTLY:
#   gunicorn manages multiple worker processes. If one worker crashes, gunicorn
#   restarts it. It also handles graceful reloads (SIGHUP), worker timeouts,
#   and process management — things uvicorn alone doesn't do in production.
#   We use uvicorn workers inside gunicorn so we keep async support.
#
# WHY SYSTEMD:
#   systemd is the OS-level process manager. If the gunicorn process crashes
#   (or the EC2 reboots), systemd restarts it automatically via Restart=always.
#   This means the app is self-healing without any cron jobs or external tools.
# =============================================================================
# Fix ownership so ec2-user can run the app
chown -R ec2-user:ec2-user "${APP_DIR}"

cat > /etc/systemd/system/gunicorn.service << 'UNIT'
[Unit]
Description=Football League MS — Gunicorn ASGI server
Documentation=https://docs.gunicorn.org
After=network.target

[Service]
User=ec2-user
Group=ec2-user
WorkingDirectory=/opt/football-league
# Reads DATABASE_URL and SECRET_KEY so gunicorn workers inherit them
EnvironmentFile=/opt/football-league/.env
ExecStart=/opt/football-league/.venv/bin/gunicorn main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 127.0.0.1:8000 \
    --access-logfile /var/log/gunicorn-access.log \
    --error-logfile /var/log/gunicorn-error.log
# Restart on any non-zero exit, with a 5-second back-off
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable gunicorn
systemctl start gunicorn

# =============================================================================
# 8. Nginx as a reverse proxy
#
# WHY NGINX IN FRONT OF GUNICORN:
#   - Gunicorn should only bind to 127.0.0.1 (localhost), never directly to
#     the public internet. Nginx is battle-hardened at handling raw HTTP,
#     TLS termination, connection limits, and static file serving.
#   - Nginx buffers slow clients so gunicorn workers aren't blocked waiting
#     for slow uploads/downloads.
#   - Later you'll add SSL termination here (certbot / ACM).
# =============================================================================
cat > /etc/nginx/conf.d/football-league.conf << 'NGINX'
server {
    listen 80;
    server_name _;

    # Pass all requests to gunicorn on localhost:8000
    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_http_version 1.1;

        # Forward real client IP to the FastAPI app
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;

        # WebSocket upgrade support (useful for future /ws endpoints)
        proxy_set_header   Upgrade           $http_upgrade;
        proxy_set_header   Connection        "upgrade";

        proxy_read_timeout 60s;
        proxy_send_timeout 60s;
    }
}
NGINX

# Remove the default nginx welcome page
rm -f /etc/nginx/conf.d/default.conf

systemctl enable nginx
systemctl restart nginx

echo "====== Setup complete. App is live at http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)/clubs/ ======"
