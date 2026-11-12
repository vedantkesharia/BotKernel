output "instance_id" {
  description = "Use this ID with an operator identity authorized for SSM StartSession; no SSH rule is configured."
  value       = aws_instance.demo.id
}

output "private_ip" {
  description = "Private VPC address for inventory; the dashboard is not bound to this address."
  value       = aws_instance.demo.private_ip
}

output "backend_repository_url" {
  description = "Private ECR backend repository. Push is a separate, explicitly authorized operation."
  value       = aws_ecr_repository.backend.repository_url
}

output "dashboard_repository_url" {
  description = "Private ECR dashboard repository. Push is a separate, explicitly authorized operation."
  value       = aws_ecr_repository.dashboard.repository_url
}

output "cloudwatch_log_group" {
  description = "Pre-created application log group; Compose must not create log groups."
  value       = aws_cloudwatch_log_group.application.name
}

output "ssm_port_forward_command" {
  description = "Template for a future, separately authorized private dashboard session."
  value       = "aws ssm start-session --target ${aws_instance.demo.id} --document-name AWS-StartPortForwardingSession --parameters '{\"portNumber\":[\"8080\"],\"localPortNumber\":[\"8080\"]}'"
}

output "safety_defaults" {
  description = "Application defaults required for the first simulator-only deployment."
  value = {
    cloud_mode                     = "mock"
    aws_deploy_allowed             = false
    bedrock_enabled                = false
    bedrock_spend_authorized       = false
    ai_action_execution_enabled    = false
    security_group_ingress_rules   = 0
    persistent_root_delete_on_term = false
  }
}
