locals {
  name = "botkernel-${var.environment}"

  common_tags = merge({
    Project     = "BotKernel"
    Environment = var.environment
    ManagedBy   = "Terraform"
    DataClass   = "Demo"
  }, var.tags)
}

resource "aws_vpc" "demo" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "${local.name}-vpc" }
}

resource "aws_internet_gateway" "demo" {
  vpc_id = aws_vpc.demo.id
  tags   = { Name = "${local.name}-igw" }
}

data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_subnet" "demo" {
  vpc_id                  = aws_vpc.demo.id
  cidr_block              = var.subnet_cidr
  availability_zone       = var.availability_zone != "" ? var.availability_zone : data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true

  tags = { Name = "${local.name}-subnet" }
}

resource "aws_route_table" "demo" {
  vpc_id = aws_vpc.demo.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.demo.id
  }

  tags = { Name = "${local.name}-routes" }
}

resource "aws_route_table_association" "demo" {
  subnet_id      = aws_subnet.demo.id
  route_table_id = aws_route_table.demo.id
}
