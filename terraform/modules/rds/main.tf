# RDS Module
# Creates PostgreSQL RDS instance for Hermes

variable "name_prefix" { type = string }
variable "vpc_id" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "instance_class" { type = string }
variable "allocated_storage" { type = number }
variable "database_name" { type = string }
variable "master_username" { type = string }
variable "backup_retention_period" { type = number }
variable "multi_az" { type = bool }
variable "deletion_protection" { type = bool }
variable "allowed_security_groups" { type = list(string) }

# Random password
resource "random_password" "master" {
  length  = 32
  special = false
}

# Store password in Secrets Manager
resource "aws_secretsmanager_secret" "db_password" {
  name = "${var.name_prefix}-db-password"
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id     = aws_secretsmanager_secret.db_password.id
  secret_string = random_password.master.result
}

# DB Subnet Group
resource "aws_db_subnet_group" "main" {
  name       = "${var.name_prefix}-db"
  subnet_ids = var.private_subnet_ids

  tags = {
    Name = "${var.name_prefix}-db-subnet-group"
  }
}

# Security Group
resource "aws_security_group" "rds" {
  name        = "${var.name_prefix}-rds"
  description = "Security group for Hermes RDS"
  vpc_id      = var.vpc_id

  dynamic "ingress" {
    for_each = var.allowed_security_groups
    content {
      description     = "PostgreSQL from ECS"
      from_port       = 5432
      to_port         = 5432
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
    Name = "${var.name_prefix}-rds"
  }
}

# Parameter Group
resource "aws_db_parameter_group" "main" {
  name   = "${var.name_prefix}-pg15"
  family = "postgres15"

  parameter {
    name  = "log_statement"
    value = "all"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "1000"
  }

  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements"
  }
}

# RDS Instance
resource "aws_db_instance" "main" {
  identifier = "${var.name_prefix}-postgres"

  engine               = "postgres"
  engine_version       = "15.4"
  instance_class       = var.instance_class
  allocated_storage    = var.allocated_storage
  max_allocated_storage = var.allocated_storage * 2
  storage_type         = "gp3"
  storage_encrypted    = true

  db_name  = var.database_name
  username = var.master_username
  password = random_password.master.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  parameter_group_name   = aws_db_parameter_group.main.name

  multi_az               = var.multi_az
  publicly_accessible    = false
  deletion_protection    = var.deletion_protection
  skip_final_snapshot    = !var.deletion_protection
  final_snapshot_identifier = var.deletion_protection ? "${var.name_prefix}-final-snapshot" : null

  backup_retention_period = var.backup_retention_period
  backup_window          = "03:00-04:00"
  maintenance_window     = "Mon:04:00-Mon:05:00"

  performance_insights_enabled          = true
  performance_insights_retention_period = 7

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  tags = {
    Name = "${var.name_prefix}-postgres"
  }
}

# Outputs
output "endpoint" {
  value = aws_db_instance.main.endpoint
}

output "connection_string" {
  value     = "postgresql://${var.master_username}@${aws_db_instance.main.endpoint}/${var.database_name}"
  sensitive = true
}

output "master_password_secret_arn" {
  value = aws_secretsmanager_secret.db_password.arn
}

output "security_group_id" {
  value = aws_security_group.rds.id
}
