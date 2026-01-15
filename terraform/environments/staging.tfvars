# Staging Environment Variables

environment = "staging"
aws_region  = "us-east-1"

# Network
vpc_id          = "vpc-xxxxxxxxx"  # Replace with actual VPC ID
certificate_arn = "arn:aws:acm:us-east-1:xxxxxxxxxxxx:certificate/xxxxxxxx"  # Replace with actual cert

# RDS
rds_instance_class    = "db.t3.medium"
rds_allocated_storage = 50

# ElastiCache
redis_node_type = "cache.t3.small"

# ECS - API
api_cpu           = 512
api_memory        = 1024
api_desired_count = 1
api_min_count     = 1
api_max_count     = 4

# ECS - gRPC
grpc_cpu           = 512
grpc_memory        = 1024
grpc_desired_count = 1

# ECS - Agent
agent_cpu    = 256
agent_memory = 512

# Application
log_level    = "DEBUG"
cors_origins = "*"

# CloudWatch
log_retention_days = 14

# Image
image_tag = "staging"
