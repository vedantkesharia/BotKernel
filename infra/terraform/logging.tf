resource "aws_cloudwatch_log_group" "application" {
  name              = "/botkernel/${var.environment}"
  retention_in_days = var.log_retention_days

  lifecycle {
    prevent_destroy = true
  }

  tags = { Name = "${local.name}-logs" }
}
