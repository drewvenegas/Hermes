# Hermes Infrastructure
# Terraform configuration for AWS ECS deployment

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "bravo-zero-terraform-state"
    key            = "hermes/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-state-lock"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "Hermes"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Team        = "BravoZero"
    }
  }
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Local values
locals {
  name_prefix = "hermes-${var.environment}"
  
  common_tags = {
    Project     = "Hermes"
    Environment = var.environment
  }
}

# ECR Repository
module "ecr" {
  source = "./modules/ecr"

  name_prefix         = local.name_prefix
  image_retention_count = var.ecr_image_retention_count
}

# VPC (use existing or create)
data "aws_vpc" "main" {
  id = var.vpc_id
}

data "aws_subnets" "private" {
  filter {
    name   = "vpc-id"
    values = [var.vpc_id]
  }

  tags = {
    Tier = "private"
  }
}

data "aws_subnets" "public" {
  filter {
    name   = "vpc-id"
    values = [var.vpc_id]
  }

  tags = {
    Tier = "public"
  }
}

# Application Load Balancer
module "alb" {
  source = "./modules/alb"

  name_prefix       = local.name_prefix
  vpc_id            = var.vpc_id
  public_subnet_ids = data.aws_subnets.public.ids
  certificate_arn   = var.certificate_arn
  health_check_path = "/health"
}

# RDS PostgreSQL
module "rds" {
  source = "./modules/rds"

  name_prefix        = local.name_prefix
  vpc_id             = var.vpc_id
  private_subnet_ids = data.aws_subnets.private.ids
  
  instance_class     = var.rds_instance_class
  allocated_storage  = var.rds_allocated_storage
  database_name      = "hermes"
  master_username    = var.db_username
  
  backup_retention_period = var.environment == "production" ? 30 : 7
  multi_az               = var.environment == "production"
  deletion_protection    = var.environment == "production"
  
  allowed_security_groups = [module.ecs.service_security_group_id]
}

# ElastiCache Redis
module "elasticache" {
  source = "./modules/elasticache"

  name_prefix        = local.name_prefix
  vpc_id             = var.vpc_id
  private_subnet_ids = data.aws_subnets.private.ids
  
  node_type          = var.redis_node_type
  num_cache_nodes    = var.environment == "production" ? 3 : 1
  
  allowed_security_groups = [module.ecs.service_security_group_id]
}

# ECS Cluster and Services
module "ecs" {
  source = "./modules/ecs"

  name_prefix        = local.name_prefix
  vpc_id             = var.vpc_id
  private_subnet_ids = data.aws_subnets.private.ids
  
  # API Service
  api_image          = "${module.ecr.repository_url}:${var.image_tag}"
  api_cpu            = var.api_cpu
  api_memory         = var.api_memory
  api_desired_count  = var.api_desired_count
  api_min_count      = var.api_min_count
  api_max_count      = var.api_max_count
  
  # gRPC Service
  grpc_image         = "${module.ecr.repository_url}:${var.image_tag}"
  grpc_cpu           = var.grpc_cpu
  grpc_memory        = var.grpc_memory
  grpc_desired_count = var.grpc_desired_count
  
  # Agent Service
  agent_image        = "${module.ecr.repository_url}:${var.image_tag}"
  agent_cpu          = var.agent_cpu
  agent_memory       = var.agent_memory
  
  # Load Balancer
  alb_target_group_arn = module.alb.target_group_arn
  
  # Environment
  environment_variables = {
    ENVIRONMENT      = var.environment
    DATABASE_URL     = module.rds.connection_string
    REDIS_URL        = module.elasticache.connection_string
    LOG_LEVEL        = var.log_level
    CORS_ORIGINS     = var.cors_origins
    GRPC_ENABLED     = "true"
    GRPC_PORT        = "50051"
  }
  
  # Secrets
  secrets = {
    DATABASE_PASSWORD = module.rds.master_password_secret_arn
    API_SECRET_KEY    = var.api_secret_key_arn
  }
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "hermes" {
  name              = "/ecs/${local.name_prefix}"
  retention_in_days = var.log_retention_days
}

# Outputs
output "alb_dns_name" {
  description = "ALB DNS name"
  value       = module.alb.dns_name
}

output "api_endpoint" {
  description = "API endpoint URL"
  value       = "https://${module.alb.dns_name}"
}

output "ecr_repository_url" {
  description = "ECR repository URL"
  value       = module.ecr.repository_url
}

output "rds_endpoint" {
  description = "RDS endpoint"
  value       = module.rds.endpoint
  sensitive   = true
}

output "redis_endpoint" {
  description = "Redis endpoint"
  value       = module.elasticache.endpoint
  sensitive   = true
}
