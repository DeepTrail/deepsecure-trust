resource "google_redis_instance" "main" {
  name           = "deepsecure-redis"
  tier           = "BASIC"
  memory_size_gb = 1
  region         = var.region
  redis_version  = "REDIS_7_0"

  authorized_network = "default"

  depends_on = [google_project_service.apis["redis.googleapis.com"]]
}
