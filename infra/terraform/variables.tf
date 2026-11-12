variable "region" {
  description = "AWS commercial region for this isolated demo. Confirm service/model availability before deployment."
  type        = string
  default     = "us-east-2"
}

variable "aws_account_id" {
  description = "12-digit account ID used to scope the CloudWatch runtime policy; never infer or discover it during validation."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{12}$", var.aws_account_id))
    error_message = "Set aws_account_id to the intended 12-digit AWS account ID."
  }
}

variable "environment" {
  description = "Short isolated environment name used in resource names and tags."
  type        = string
  default     = "demo"

  validation {
    condition     = can(regex("^[a-z0-9-]{1,16}$", var.environment))
    error_message = "environment must be 1-16 lowercase letters, digits, or hyphens."
  }
}

variable "ami_id" {
  description = "Reviewed Amazon Linux 2023 x86_64 AMI ID for the selected region; deliberately supplied by the operator."
  type        = string

  validation {
    condition     = can(regex("^ami-[0-9a-f]{8,17}$", var.ami_id))
    error_message = "ami_id must be a real-looking AMI ID selected for region."
  }
}

variable "instance_type" {
  description = "Single-host demo size. m7i-flex.large is the Free Tier eligible 2-vCPU, 8-GiB target."
  type        = string
  default     = "m7i-flex.large"
}

variable "vpc_cidr" {
  description = "Dedicated IPv4 CIDR for the single-host VPC."
  type        = string
  default     = "10.42.0.0/16"
}

variable "subnet_cidr" {
  description = "Single public-routing subnet; the instance security group has no ingress rules."
  type        = string
  default     = "10.42.1.0/24"
}

variable "availability_zone" {
  description = "Optional AZ override. Empty selects the first available AZ in region."
  type        = string
  default     = ""
}

variable "root_volume_size_gib" {
  description = "Encrypted gp3 root/data volume. It is intentionally retained when the instance is terminated."
  type        = number
  default     = 100

  validation {
    condition     = var.root_volume_size_gib >= 40 && var.root_volume_size_gib <= 500
    error_message = "root_volume_size_gib must be between 40 and 500 GiB."
  }
}

variable "enable_ssm" {
  description = "Attach the managed-node policy needed for authenticated SSM administration and port forwarding."
  type        = bool
  default     = true
}

variable "enable_bedrock_invoke" {
  description = "Attach the separate, model-resource-scoped Converse permission. Keep false until separately approved."
  type        = bool
  default     = false

  validation {
    condition     = !var.enable_bedrock_invoke || length(var.bedrock_model_arns) > 0
    error_message = "Bedrock invocation requires explicit foundation-model/inference-profile ARNs."
  }
}

variable "bedrock_model_arns" {
  description = "Exact foundation-model and/or inference-profile ARNs required by the approved Converse model."
  type        = list(string)
  default     = []

  validation {
    condition = alltrue([
      for arn in var.bedrock_model_arns :
      startswith(arn, "arn:aws:bedrock:") && can(regex(":(foundation-model|inference-profile)/", arn))
    ])
    error_message = "Each Bedrock resource must be an explicit commercial-region foundation-model or inference-profile ARN."
  }
}

variable "log_retention_days" {
  description = "CloudWatch application log retention."
  type        = number
  default     = 30

  validation {
    condition     = contains([7, 14, 30, 60, 90], var.log_retention_days)
    error_message = "Choose one supported short retention period: 7, 14, 30, 60, or 90 days."
  }
}

variable "tags" {
  description = "Additional non-sensitive resource tags."
  type        = map(string)
  default     = {}
}

