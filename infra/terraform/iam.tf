data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "runtime" {
  name               = "${local.name}-runtime"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json
  description        = "Application runtime role only; it is not an infrastructure-administration role."
}

resource "aws_iam_instance_profile" "runtime" {
  name = "${local.name}-runtime"
  role = aws_iam_role.runtime.name
}

resource "aws_iam_role_policy_attachment" "ssm" {
  count      = var.enable_ssm ? 1 : 0
  role       = aws_iam_role.runtime.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_policy" "runtime" {
  name        = "${local.name}-runtime"
  description = "Pull only BotKernel images and write only the BotKernel CloudWatch log group."
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "EcrAuthorization"
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Sid    = "PullBotKernelImages"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer"
        ]
        Resource = [
          aws_ecr_repository.backend.arn,
          aws_ecr_repository.dashboard.arn
        ]
      },
      {
        Sid    = "WriteApplicationLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.application.arn}:*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "runtime" {
  role       = aws_iam_role.runtime.name
  policy_arn = aws_iam_policy.runtime.arn
}

resource "aws_iam_policy" "bedrock_invoke" {
  count       = var.enable_bedrock_invoke ? 1 : 0
  name        = "${local.name}-bedrock-invoke"
  description = "Optional Converse permission restricted to explicitly configured model/profile ARNs."
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "InvokeApprovedModelsOnly"
      Effect   = "Allow"
      Action   = ["bedrock:InvokeModel"]
      Resource = var.bedrock_model_arns
    }]
  })
}

resource "aws_iam_role_policy_attachment" "bedrock_invoke" {
  count      = var.enable_bedrock_invoke ? 1 : 0
  role       = aws_iam_role.runtime.name
  policy_arn = aws_iam_policy.bedrock_invoke[0].arn
}
