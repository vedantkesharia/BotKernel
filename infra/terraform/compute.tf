resource "aws_instance" "demo" {
  ami                         = var.ami_id
  instance_type               = var.instance_type
  subnet_id                   = aws_subnet.demo.id
  vpc_security_group_ids      = [aws_security_group.instance.id]
  iam_instance_profile        = aws_iam_instance_profile.runtime.name
  associate_public_ip_address = true
  monitoring                  = false
  user_data                   = file("${path.module}/user_data.sh")


  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
    instance_metadata_tags      = "disabled"
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.root_volume_size_gib
    encrypted             = true
    delete_on_termination = false
  }

  volume_tags = { Name = "${local.name}-persistent-root" }
  tags = {
    Name     = "${local.name}-host"
    Runtime  = "DockerCompose"
    DataPath = "/var/lib/docker"
  }

  depends_on = [
    aws_iam_role_policy_attachment.runtime,
    aws_route_table_association.demo
  ]
}
