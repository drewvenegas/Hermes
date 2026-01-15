# Production Environment Variables

environment = "production"
aws_region  = "us-east-1"

# Network
vpc_id          = "vpc-xxxxxxxxx"  # Replace with actual VPC ID
certificate_arn = "arn:aws:acm:us-east-1:xxxxxxxxxxxx:certificate/xxxxxxxx"  # Replace with actual cert

# RDS
rds_instance_class    = "db.r6g.large"
rds_allocated_storage = 200

# ElastiCache
redis_node_type = "cache.r6g.large"

# ECS - API
api_cpu           = 1024
api_memory        = 2048
api_desired_count = 3
api_min_count     = 2
api_max_count     = 20

# ECS - gRPC
grpc_cpu           = 1024
grpc_memory        = 2048
grpc_desired_count = 3

# ECS - Agent
agent_cpu    = 512
agent_memory = 1024

# Application
log_level    = "INFO"
cors_origins = "https://hermes.bravo-zero.io,https://hydra.bravo-zero.io"

# CloudWatch
log_retention_days = 90

# Image
image_tag = "latest"
