#!/bin/bash
# =============================================================================
# Football League MS — EC2 first-boot setup script
#
# Variables injected by CDK at the top of the user data:
#   USE_RDS   "true"  → fetch DB password from Secrets Manager (RDS mode)
#             "false" → install PostgreSQL on this server (EC2-local mode)
#   APP_DIR, REPO_URL, DB_HOST, DB_PORT, DB_NAME, DB_USER, SECRET_ARN
#   SQS_QUEUE_URL, COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID,
#   COGNITO_REGION, COGNITO_JWKS_URL
# =============================================================================
set -euxo pipefail
exec > >(tee /var/log/user-data.log | logger -t user-data) 2>&1

# =============================================================================
# 1. System packages
# =============================================================================
dnf update -y
dnf install -y python3.11 python3.11-pip git nginx

# Make python3.11 the default python3
alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# =============================================================================
# 2. Clone the application repo
#
# GIT_TERMINAL_PROMPT=0 prevents git from hanging waiting for credentials
# when there is no TTY (which is always the case in user-data).  For a public
# repo this is harmless; for a private repo it surfaces a clear auth error
# instead of a silent hang.
# =============================================================================
export GIT_TERMINAL_PROMPT=0
git clone "${REPO_URL}" "${APP_DIR}"
cd "${APP_DIR}"
git checkout main

# =============================================================================
# 3. Python virtual environment and dependencies
# =============================================================================
python3.11 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# =============================================================================
# 4. Database setup
#
# Two modes, both end with $DB_PASSWORD set and the DB ready to accept
# connections at postgresql://$DB_USER:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME
# =============================================================================

if [ "${USE_RDS}" = "true" ]; then
    # -------------------------------------------------------------------------
    # RDS mode: fetch credentials from AWS Secrets Manager via the IAM role.
    #
    # WHY NOT STORE THE PASSWORD IN GIT / .env IN THE REPO:
    #   Anything committed to git is permanent. Even if you delete it later,
    #   the password lives in the git history forever. Secrets Manager stores
    #   it encrypted, access is audited, and only this EC2's IAM role can
    #   read it. No human ever types or sees the password.
    # -------------------------------------------------------------------------
    DB_PASSWORD=$(
        aws secretsmanager get-secret-value \
            --secret-id "${SECRET_ARN}" \
            --query SecretString \
            --output text \
        | python3.11 -c "import sys, json; print(json.loads(sys.stdin.read())['password'])"
    )

else
    # -------------------------------------------------------------------------
    # EC2-local mode: install PostgreSQL 15 on this server.
    #
    # WHY THIS IS FINE FOR LEARNING / DEVELOPMENT:
    #   The app doesn't know the difference — DATABASE_URL just points to
    #   localhost instead of an RDS hostname. The trade-off is that if this
    #   EC2 is terminated, the data is gone. For production, switch to RDS
    #   (set use_rds=true in cdk.json) which handles backups, failover, etc.
    # -------------------------------------------------------------------------

    # Install PostgreSQL 15 from the Amazon Linux 2023 repository.
    # AL2023 ships postgresql15-server with binaries in /usr/bin/ and the
    # setup helper at /usr/bin/postgresql-setup (unlike the PGDG packages
    # which put everything in /usr/pgsql-15/bin/).
    dnf install -y postgresql15-server postgresql15

    # Initialise the database cluster (creates /var/lib/pgsql/data/).
    postgresql-setup --initdb

    # Configure password authentication for TCP connections.
    # We keep "peer" for local Unix-socket connections so that
    # "sudo -u postgres psql" keeps working without a password.
    # Only the "ident" entries on TCP host lines are changed to "md5"
    # so the app can connect with a password via DATABASE_URL.
    PG_HBA="/var/lib/pgsql/data/pg_hba.conf"
    sed -i '/^host/s/\bident\b/md5/g' "${PG_HBA}"

    systemctl enable postgresql
    systemctl start postgresql
    sleep 3

    # Generate a random password (stored only in .env, never in git)
    DB_PASSWORD=$(python3.11 -c "import secrets; print(secrets.token_hex(16))")

    # Create the application database and set the postgres password.
    # "sudo -u postgres psql" works because the local socket still uses peer auth.
    sudo -u postgres psql -c \
        "ALTER USER postgres WITH PASSWORD '${DB_PASSWORD}';"
    sudo -u postgres psql -c \
        "CREATE DATABASE ${DB_NAME};"
fi

# =============================================================================
# 5. Create .env file
#
# WHY .env NEVER GOES IN GIT:
#   DATABASE_URL contains the DB password.
#   SECRET_KEY is used to sign authentication tokens — if leaked, anyone
#   can forge valid tokens. The .env file is in .gitignore; .env.example
#   (with placeholder values) IS committed as a template.
# =============================================================================
cat > "${APP_DIR}/.env" << EOF
DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}
SECRET_KEY=$(python3.11 -c "import secrets; print(secrets.token_hex(32))")
# Phase 4 — S3 / CloudFront (values injected by CDK at EC2 boot time)
S3_BUCKET_NAME=${S3_BUCKET_NAME}
CLOUDFRONT_DOMAIN=${CLOUDFRONT_DOMAIN}
# Phase 5 — SQS notification queue
SQS_QUEUE_URL=${SQS_QUEUE_URL}
COGNITO_USER_POOL_ID=${COGNITO_USER_POOL_ID}
COGNITO_CLIENT_ID=${COGNITO_CLIENT_ID}
COGNITO_REGION=${COGNITO_REGION}
COGNITO_JWKS_URL=${COGNITO_JWKS_URL}
EOF
chmod 600 "${APP_DIR}/.env"

# =============================================================================
# 6. Run Alembic migrations
#
# Creates all tables in the database. We retry a few times because in RDS mode
# the instance may still be initialising even after CloudFormation says COMPLETE.
# In EC2-local mode it retries in case PostgreSQL is still starting up.
# =============================================================================
export DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

for attempt in 1 2 3 4 5; do
    echo "Migration attempt ${attempt}/5..."
    if "${APP_DIR}/.venv/bin/alembic" upgrade head; then
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
# WHY GUNICORN + UVICORN WORKERS:
#   gunicorn manages multiple worker processes — if one crashes, it restarts
#   it. uvicorn workers inside gunicorn keep async support. Running gunicorn
#   as a systemd service means it restarts automatically on crash or reboot.
# =============================================================================
chown -R ec2-user:ec2-user "${APP_DIR}"

# Create log files owned by ec2-user so gunicorn can write them at start-up.
touch /var/log/gunicorn-access.log /var/log/gunicorn-error.log
chown ec2-user:ec2-user /var/log/gunicorn-access.log /var/log/gunicorn-error.log

cat > /etc/systemd/system/gunicorn.service << 'UNIT'
[Unit]
Description=Football League MS - Gunicorn ASGI server
After=network.target

[Service]
User=ec2-user
Group=ec2-user
WorkingDirectory=/opt/football-league
EnvironmentFile=/opt/football-league/.env
ExecStart=/opt/football-league/.venv/bin/gunicorn main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 127.0.0.1:8000 \
    --access-logfile /var/log/gunicorn-access.log \
    --error-logfile /var/log/gunicorn-error.log
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable gunicorn
systemctl start gunicorn

# =============================================================================
# 8. Nginx as reverse proxy
#
# WHY NGINX IN FRONT OF GUNICORN:
#   Gunicorn binds to 127.0.0.1 (localhost only). Nginx handles the public
#   port 80, buffers slow clients, and is where you'll add TLS (HTTPS) later.
# =============================================================================
cat > /etc/nginx/conf.d/football-league.conf << 'NGINX'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
        proxy_send_timeout 60s;
    }
}
NGINX

rm -f /etc/nginx/conf.d/default.conf
systemctl enable nginx
systemctl restart nginx

PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)
echo "====== Setup complete. Test: curl http://${PUBLIC_IP}/clubs/ ======"
