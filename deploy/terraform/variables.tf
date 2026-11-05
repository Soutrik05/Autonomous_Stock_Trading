variable "region" {
  type    = string
  default = "ap-south-1" # Mumbai: closest to Kolkata and to NSE/Upstox
}

variable "instance_type" {
  type        = string
  default     = "t3.medium" # 4 GB RAM: FinBERT (torch CPU) + scheduler + API. t3.small (2 GB) is tight.
  description = "EC2 size. Cost is roughly USD 30/month on-demand for t3.medium; check the AWS pricing page."
}

variable "data_volume_gb" {
  type    = number
  default = 20
}

variable "github_repo" {
  type        = string
  description = "owner/repo allowed to deploy via GitHub Actions OIDC, e.g. Soumik-05/Autonomous_Stock_Trading"
}

variable "github_branch" {
  type    = string
  default = "v2-ATA"
}

variable "create_github_oidc_provider" {
  type        = bool
  default     = true
  description = "Set false if your AWS account already has the token.actions.githubusercontent.com OIDC provider."
}

variable "backup_bucket_name" {
  type        = string
  description = "Globally unique S3 bucket name for nightly portfolio.db backups."
}
