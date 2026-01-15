# ElastiCache Module
# Creates Redis cluster for Hermes caching

variable "name_prefix" { type = string }
variable "vpc_id" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "node_type" { type = string }
variable "num_cache_nodes" { type = number }
variable "allowed_security_groups" { type = list(string) }

# Subnet Group
resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.name_prefix}-redis"
  subnet_ids = var.private_subnet_ids
}

# Security Group
resource "aws_security_group" "redis" {
  name        = "${var.name_prefix}-redis"
  description = "Security group for Hermes Redis"
  vpc_id      = var.vpc_id

  dynamic "ingress" {
    for_each = var.allowed_security_groups
    content {
      description     = "Redis from ECS"
      from_port       = 6379
      to_port         = 6379
      protocol        = "tcp"
      security_groups = [ingress.value]
    }
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.name_prefix}-redis"
  }
}

# Parameter Group
resource "aws_elasticache_parameter_group" "main" {
  name   = "${var.name_prefix}-redis7"
  family = "redis7"

  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }
}

# Redis Cluster
resource "aws_elasticache_cluster" "main" {
  cluster_id           = "${var.name_prefix}-redis"
  engine               = "redis"
  engine_version       = "7.0"
  node_type            = var.node_type
  num_cache_nodes      = var.num_cache_nodes
  parameter_group_name = aws_elasticache_parameter_group.main.name
  port                 = 6379

  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.redis.id]

  snapshot_retention_limit = 7
  snapshot_window          = "05:00-06:00"
  maintenance_window       = "sun:06:00-sun:07:00"

  tags = {
    Name = "${var.name_prefix}-redis"
  }
}

# Outputs
output "endpoint" {
  value = aws_elasticache_cluster.main.cache_nodes[0].address
}

output "connection_string" {
  value     = "redis://${aws_elasticache_cluster.main.cache_nodes[0].address}:6379"
  sensitive = true
}

output "security_group_id" {
  value = aws_security_group.redis.id
}
