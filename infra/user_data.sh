#!/bin/bash
# =============================================================================
# Football League MS — EC2 first-boot setup script
#
# Variables injected by CDK at the top of the user data:
#   USE_RDS   "true"  → fetch DB password from Secrets Manager (RDS mode)
#             "false" → install PostgreSQL on this server (EC2-local mode)
#   APP_DIR, REPO_URL, DB_HOST, DB_PORT, DB_NAME, DB_USER, SECRET_ARN
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
# =============================================================================
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

    # Install from the official PostgreSQL Global Development Group (PGDG) repo
    # so we get known, stable paths regardless of AL2023 package naming.
    dnf install -y \
        https://download.postgresql.org/pub/repos/yum/reporpms/EL-9-x86_64/pgdg-redhat-repo-latest.noarch.rpm
    dnf -qy module disable postgresql
    dnf install -y postgresql15-server postgresql15

    # Initialise the database cluster
    /usr/pgsql-15/bin/postgresql-15-setup initdb

    # Configure password authentication over localhost.
    # AL2023 defaults to "ident" (Unix socket user must match PG user),
    # which doesn't work with a password in DATABASE_URL.
    PG_HBA="/var/lib/pgsql/15/data/pg_hba.conf"
    sed -i 's/ident/md5/g'  "${PG_HBA}"
    sed -i 's/\bpeer\b/md5/g' "${PG_HBA}"

    systemctl enable postgresql-15
    systemctl start postgresql-15

    # Generate a random password (stored only in .env, never in git)
    DB_PASSWORD=$(python3.11 -c "import secrets; print(secrets.token_hex(16))")

    # Create the application database user and database
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
