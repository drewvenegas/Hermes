# Hermes Terraform Variables

# General
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (staging, production)"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "certificate_arn" {
  description = "ACM certificate ARN for HTTPS"
  type        = string
}

# ECR
variable "ecr_image_retention_count" {
  description = "Number of images to retain in ECR"
  type        = number
  default     = 30
}

variable "image_tag" {
  description = "Docker image tag to deploy"
  type        = string
  default     = "latest"
}

# RDS
variable "rds_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.medium"
}

variable "rds_allocated_storage" {
  description = "RDS allocated storage in GB"
  type        = number
  default     = 100
}

variable "db_username" {
  description = "Database master username"
  type        = string
  default     = "hermes"
  sensitive   = true
}

# ElastiCache
variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t3.medium"
}

# ECS - API Service
variable "api_cpu" {
  description = "API task CPU units"
  type        = number
  default     = 512
}

variable "api_memory" {
  description = "API task memory in MB"
  type        = number
  default     = 1024
}

variable "api_desired_count" {
  description = "Desired number of API tasks"
  type        = number
  default     = 2
}

variable "api_min_count" {
  description = "Minimum number of API tasks"
  type        = number
  default     = 1
}

variable "api_max_count" {
  description = "Maximum number of API tasks"
  type        = number
  default     = 10
}

# ECS - gRPC Service
variable "grpc_cpu" {
  description = "gRPC task CPU units"
  type        = number
  default     = 512
}

variable "grpc_memory" {
  description = "gRPC task memory in MB"
  type        = number
  default     = 1024
}

variable "grpc_desired_count" {
  description = "Desired number of gRPC tasks"
  type        = number
  default     = 2
}

# ECS - Agent Service
variable "agent_cpu" {
  description = "Agent task CPU units"
  type        = number
  default     = 256
}

variable "agent_memory" {
  description = "Agent task memory in MB"
  type        = number
  default     = 512
}

# Application
variable "log_level" {
  description = "Application log level"
  type        = string
  default     = "INFO"
}

variable "cors_origins" {
  description = "CORS allowed origins"
  type        = string
  default     = "*"
}

variable "api_secret_key_arn" {
  description = "ARN of the API secret key in Secrets Manager"
  type        = string
}

# CloudWatch
variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}
