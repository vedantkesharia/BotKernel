resource "aws_security_group" "instance" {
  name        = "${local.name}-instance"
  description = "BotKernel demo: no inbound access; SSM and service egress only."
  vpc_id      = aws_vpc.demo.id

  egress {
    description = "HTTPS egress for SSM, ECR pulls, logs, package updates, and optional Bedrock."
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.name}-instance" }
}
