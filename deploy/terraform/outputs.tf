output "public_ip" { value = aws_eip.app.public_ip }
output "instance_id" { value = aws_instance.app.id }
output "ecr_app" { value = aws_ecr_repository.app.repository_url }
output "ecr_web" { value = aws_ecr_repository.web.repository_url }
output "backup_bucket" { value = aws_s3_bucket.backups.bucket }
output "github_deploy_role_arn" { value = aws_iam_role.github_deploy.arn }
