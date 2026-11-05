# Deploying StockMinds to AWS (single EC2 + Docker)

**What you get:** one EC2 instance in Mumbai (`ap-south-1`) running three containers behind Caddy:
`scheduler` (your APScheduler engine), `api` (read-only FastAPI) and `web` (React dashboard + HTTPS proxy).
SQLite stays as is, on an encrypted EBS disk that survives instance replacement. Nightly `portfolio.db`
backups go to S3, plus daily EBS snapshots. No SSH: you get a shell through SSM Session Manager.

```
Internet -> Caddy :80/:443 -> /api/* -> api:8000 (read-only SQLite)
                           -> /*     -> dashboard (static)
scheduler (only writer) ---> /opt/stockminds/storage (EBS) <--- api reads
```

Approximate cost: t3.medium about USD 30/month, plus about USD 2 for disk and snapshots (check AWS pricing).
Use `-var instance_type=t3.small` to save money, but FinBERT may run out of memory.

## 0. Before anything: rotate your keys
Your project zip contained a live `.env` (Upstox, Groq, Gemini). It is gitignored, but rotate those keys if the
zip was ever shared. Never commit `.env`.

## 1. Apply the changes in Antigravity
```bash
git checkout v2-ATA
git apply stockminds-backend.patch      # or copy the files from stockminds-backend-files.zip
pip install -r requirements.txt
pytest tests -q
```
Run it locally first:
```bash
PYTHONPATH=src:. uvicorn api.main:app --reload     # http://localhost:8000/docs
```

## 2. Create the AWS infrastructure (once)
Prerequisites: an AWS account, AWS CLI configured (`aws configure`), Terraform >= 1.5.
```bash
cd deploy/terraform
terraform init
terraform apply \
  -var github_repo=<owner>/<repo> \
  -var backup_bucket_name=<globally-unique-name>
```
If your account already has a GitHub OIDC provider, add `-var create_github_oidc_provider=false`.
Note the outputs: `public_ip`, `instance_id`, `github_deploy_role_arn`.

## 3. Put your secrets and existing data on the server
Open a shell (no SSH key needed): AWS Console -> EC2 -> your instance -> Connect -> Session Manager.
```bash
sudo -i
cd /opt/stockminds
nano .env       # paste your .env, then add the lines below
```
Add to `.env`:
```
S3_BACKUP_BUCKET=<your bucket name>
API_CORS_ORIGINS=https://<your-domain-or-http://PUBLIC_IP>
SITE_ADDRESS=:80            # or your domain for automatic HTTPS
# API_KEY=...               # optional; locks /api/* except /api/health
```
**Move your existing ledger** so the paper-trading history continues. From your computer:
```bash
aws s3 cp storage/ledger/portfolio.db s3://<bucket>/seed/portfolio.db
aws s3 cp --recursive storage/market s3://<bucket>/seed/market
```
Then on the server:
```bash
cd /opt/stockminds
mkdir -p storage/ledger storage/market
aws s3 cp s3://<bucket>/seed/portfolio.db storage/ledger/portfolio.db
aws s3 cp --recursive s3://<bucket>/seed/market storage/market
chown -R 1000:1000 /mnt/data
```
Do not run the scheduler locally and on AWS against separate copies at the same time, or the two ledgers diverge.

## 4. Wire up GitHub Actions
In the repo: Settings -> Secrets and variables -> Actions -> **Variables**:
`AWS_REGION=ap-south-1`, `AWS_DEPLOY_ROLE_ARN=<github_deploy_role_arn>`, `EC2_INSTANCE_ID=<instance_id>`.
Then Actions -> "Deploy to AWS" -> Run workflow (branch `v2-ATA`). It builds both images, pushes them to ECR,
and rolls them out over SSM. The AWS role only trusts that branch, matching your "never push to main" rule.

## 5. Check it
```bash
curl http://<public_ip>/api/health         # {"status":"ok"|"degraded", jobs: [...]}
curl http://<public_ip>/api/leaderboard
```
`http://<public_ip>/docs` shows the interactive API docs. For a domain, point an A record at `public_ip`,
set `SITE_ADDRESS=yourdomain.com` in `.env`, and redeploy; Caddy gets the certificate by itself.

## Operations
- Logs: `docker logs -f stockminds_scheduler` (via Session Manager).
- Restore a backup: download `portfolio-backups/portfolio_<date>.db` from S3, stop the scheduler, replace
  `storage/ledger/portfolio.db`, start it again.
- Schema changes: add a numbered file in `db/migrations/` as your CLAUDE.md requires; never edit the live DB by hand.
- Teardown: the data disk has `prevent_destroy`, so `terraform destroy` refuses to delete your ledger. Remove it
  deliberately if you mean to.

## API reference (read-only, all GET)
`/api/leaderboard`, `/api/agents`, `/api/agents/{id}/positions|orders|decisions|nav|memory`,
`/api/baseline/comparison`, `/api/activity`, `/api/health`, `/healthz`. List endpoints take `limit` and `offset`
(max 500); `/api/activity` takes `before_id` for paging. Money fields are integer paise (`*_paise`).
