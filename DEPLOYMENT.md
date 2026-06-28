# Kairon Flow Deployment Guide (Railway.app)

Follow these step-by-step instructions to deploy Kairon Flow to Railway:

## Prerequisites
1. Sign up for an account at [railway.app](https://railway.app/).
2. Install the Railway CLI:
   ```bash
   npm install -g @railway/cli
   ```

## Deploying the Stack
1. **Authenticate the CLI**:
   ```bash
   railway login
   ```
2. **Initialize Railway Project**:
   Run in the root folder of the project:
   ```bash
   railway init
   ```
3. **Provision Database**:
   Add a PostgreSQL plugin service in the Railway project dashboard.
4. **Configure Environment Variables**:
   In the Railway web interface, configure the following variables under service settings:
   - `SECRET_KEY`: (Provide a secure randomly generated key)
   - `DEBUG`: `False`
   - `ALLOWED_HOSTS`: `*` (or your railway app domain name)
   - `DATABASE_URL`: (Automatically provided by provisioning the PostgreSQL service)
   - `SECURE_SSL_REDIRECT`: `True`
   - `SESSION_COOKIE_SECURE`: `True`
   - `CSRF_COOKIE_SECURE`: `True`
5. **Upload the Application**:
   ```bash
   railway up
   ```
6. **Apply Django Database Migrations**:
   ```bash
   railway run python manage.py migrate
   ```
