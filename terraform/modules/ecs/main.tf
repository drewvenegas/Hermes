# ECS Module
# Creates ECS cluster, task definitions, and services for Hermes

variable "name_prefix" { type = string }
variable "vpc_id" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "api_image" { type = string }
variable "api_cpu" { type = number }
variable "api_memory" { type = number }
variable "api_desired_count" { type = number }
variable "api_min_count" { type = number }
variable "api_max_count" { type = number }
variable "grpc_image" { type = string }
variable "grpc_cpu" { type = number }
variable "grpc_memory" { type = number }
variable "grpc_desired_count" { type = number }
variable "agent_image" { type = string }
variable "agent_cpu" { type = number }
variable "agent_memory" { type = number }
variable "alb_target_group_arn" { type = string }
variable "environment_variables" { type = map(string) }
variable "secrets" { type = map(string) }

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "${var.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name = aws_ecs_cluster.main.name

  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    base              = 1
    weight            = 100
    capacity_provider = "FARGATE"
  }
}

# IAM Role for ECS Tasks
resource "aws_iam_role" "ecs_task_execution" {
  name = "${var.name_prefix}-task-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_task_execution_secrets" {
  name = "${var.name_prefix}-secrets-access"
  role = aws_iam_role.ecs_task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue"
      ]
      Resource = values(var.secrets)
    }]
  })
}

resource "aws_iam_role" "ecs_task" {
  name = "${var.name_prefix}-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

# Security Group
resource "aws_security_group" "ecs_service" {
  name        = "${var.name_prefix}-ecs-service"
  description = "Security group for Hermes ECS services"
  vpc_id      = var.vpc_id

  ingress {
    description = "HTTP from ALB"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"]
  }

  ingress {
    description = "gRPC"
    from_port   = 50051
    to_port     = 50051
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.name_prefix}-ecs-service"
  }
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/${var.name_prefix}"
  retention_in_days = 30
}

# API Task Definition
resource "aws_ecs_task_definition" "api" {
  family                   = "${var.name_prefix}-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.api_cpu
  memory                   = var.api_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name  = "api"
    image = var.api_image
    
    portMappings = [{
      containerPort = 8000
      hostPort      = 8000
      protocol      = "tcp"
    }]
    
    environment = [for k, v in var.environment_variables : { name = k, value = v }]
    
    secrets = [for k, v in var.secrets : { name = k, valueFrom = v }]
    
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
        "awslogs-region"        = data.aws_region.current.name
        "awslogs-stream-prefix" = "api"
      }
    }
    
    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 60
    }
  }])
}

# API Service
resource "aws_ecs_service" "api" {
  name            = "${var.name_prefix}-api"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.ecs_service.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = var.alb_target_group_arn
    container_name   = "api"
    container_port   = 8000
  }

  deployment_configuration {
    maximum_percent         = 200
    minimum_healthy_percent = 100
  }

  lifecycle {
    ignore_changes = [desired_count]
  }
}

# API Auto Scaling
resource "aws_appautoscaling_target" "api" {
  max_capacity       = var.api_max_count
  min_capacity       = var.api_min_count
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "api_cpu" {
  name               = "${var.name_prefix}-api-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.api.resource_id
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
  service_namespace  = aws_appautoscaling_target.api.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = 70.0
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}

# gRPC Task Definition
resource "aws_ecs_task_definition" "grpc" {
  family                   = "${var.name_prefix}-grpc"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.grpc_cpu
  memory                   = var.grpc_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name  = "grpc"
    image = var.grpc_image
    
    command = ["python", "-m", "hermes.grpc.server"]
    
    portMappings = [{
      containerPort = 50051
      hostPort      = 50051
      protocol      = "tcp"
    }]
    
    environment = [for k, v in var.environment_variables : { name = k, value = v }]
    
    secrets = [for k, v in var.secrets : { name = k, valueFrom = v }]
    
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
        "awslogs-region"        = data.aws_region.current.name
        "awslogs-stream-prefix" = "grpc"
      }
    }
  }])
}

# gRPC Service
resource "aws_ecs_service" "grpc" {
  name            = "${var.name_prefix}-grpc"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.grpc.arn
  desired_count   = var.grpc_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.ecs_service.id]
    assign_public_ip = false
  }

  service_registries {
    registry_arn = aws_service_discovery_service.grpc.arn
  }
}

# Service Discovery for gRPC
resource "aws_service_discovery_private_dns_namespace" "hermes" {
  name        = "hermes.local"
  description = "Hermes internal service discovery"
  vpc         = var.vpc_id
}

resource "aws_service_discovery_service" "grpc" {
  name = "grpc"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.hermes.id

    dns_records {
      ttl  = 10
      type = "A"
    }

    routing_policy = "MULTIVALUE"
  }

  health_check_custom_config {
    failure_threshold = 1
  }
}

# Agent Task Definition
resource "aws_ecs_task_definition" "agent" {
  family                   = "${var.name_prefix}-agent"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.agent_cpu
  memory                   = var.agent_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name  = "agent"
    image = var.agent_image
    
    command = ["python", "-m", "hermes.agents.run"]
    
    environment = concat(
      [for k, v in var.environment_variables : { name = k, value = v }],
      [{ name = "AGENT_MODE", value = "continuous" }]
    )
    
    secrets = [for k, v in var.secrets : { name = k, valueFrom = v }]
    
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
        "awslogs-region"        = data.aws_region.current.name
        "awslogs-stream-prefix" = "agent"
      }
    }
  }])
}

# Agent Service
resource "aws_ecs_service" "agent" {
  name            = "${var.name_prefix}-agent"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.agent.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.ecs_service.id]
    assign_public_ip = false
  }
}

# Data sources
data "aws_region" "current" {}

# Outputs
output "cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "cluster_arn" {
  value = aws_ecs_cluster.main.arn
}

output "api_service_name" {
  value = aws_ecs_service.api.name
}

output "service_security_group_id" {
  value = aws_security_group.ecs_service.id
}

output "grpc_service_discovery_name" {
  value = "${aws_service_discovery_service.grpc.name}.${aws_service_discovery_private_dns_namespace.hermes.name}"
}
