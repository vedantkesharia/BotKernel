resource "aws_ecr_repository" "backend" {
  name                 = "${local.name}-backend"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = { Name = "${local.name}-backend" }
}

resource "aws_ecr_repository" "dashboard" {
  name                 = "${local.name}-dashboard"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = { Name = "${local.name}-dashboard" }
}
