# ---------------------------------------------------------------------------
# Global External Application Load Balancer with path-based routing
# ---------------------------------------------------------------------------

resource "google_compute_global_address" "lb" {
  name    = "deepsecure-lb-ip"
  project = var.project_id

  depends_on = [google_project_service.apis["compute.googleapis.com"]]
}

resource "google_compute_managed_ssl_certificate" "main" {
  name    = "deepsecure-cert-v2"
  project = var.project_id

  managed {
    domains = [var.domain]
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [google_project_service.apis["compute.googleapis.com"]]
}

# ---------------------------------------------------------------------------
# Serverless NEGs (one per Cloud Run service)
# ---------------------------------------------------------------------------

resource "google_compute_region_network_endpoint_group" "frontend" {
  name                  = "neg-frontend"
  region                = var.region
  project               = var.project_id
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.frontend.name
  }
}

resource "google_compute_region_network_endpoint_group" "control" {
  name                  = "neg-control"
  region                = var.region
  project               = var.project_id
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.control.name
  }
}

resource "google_compute_region_network_endpoint_group" "gateway" {
  name                  = "neg-gateway"
  region                = var.region
  project               = var.project_id
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.gateway.name
  }
}

resource "google_compute_region_network_endpoint_group" "keycloak" {
  name                  = "neg-keycloak"
  region                = var.region
  project               = var.project_id
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.keycloak.name
  }
}

# ---------------------------------------------------------------------------
# Backend services
# ---------------------------------------------------------------------------

resource "google_compute_backend_service" "frontend" {
  name                  = "backend-frontend"
  project               = var.project_id
  protocol              = "HTTPS"
  load_balancing_scheme = "EXTERNAL_MANAGED"

  backend {
    group = google_compute_region_network_endpoint_group.frontend.id
  }
}

resource "google_compute_backend_service" "control" {
  name                  = "backend-control"
  project               = var.project_id
  protocol              = "HTTPS"
  load_balancing_scheme = "EXTERNAL_MANAGED"

  backend {
    group = google_compute_region_network_endpoint_group.control.id
  }
}

resource "google_compute_backend_service" "gateway" {
  name                  = "backend-gateway"
  project               = var.project_id
  protocol              = "HTTPS"
  load_balancing_scheme = "EXTERNAL_MANAGED"

  backend {
    group = google_compute_region_network_endpoint_group.gateway.id
  }
}

resource "google_compute_backend_service" "keycloak" {
  name                  = "backend-keycloak"
  project               = var.project_id
  protocol              = "HTTPS"
  load_balancing_scheme = "EXTERNAL_MANAGED"

  backend {
    group = google_compute_region_network_endpoint_group.keycloak.id
  }
}

# ---------------------------------------------------------------------------
# URL Map (path-based routing)
# ---------------------------------------------------------------------------

resource "google_compute_url_map" "main" {
  name            = "deepsecure-url-map"
  project         = var.project_id
  default_service = google_compute_backend_service.frontend.id

  host_rule {
    hosts        = [var.domain]
    path_matcher = "deepsecure"
  }

  path_matcher {
    name            = "deepsecure"
    default_service = google_compute_backend_service.frontend.id

    path_rule {
      paths   = ["/api/v1/*"]
      service = google_compute_backend_service.control.id
    }

    path_rule {
      paths   = ["/mcp", "/mcp/*"]
      service = google_compute_backend_service.gateway.id
    }

    path_rule {
      paths   = ["/realms/*"]
      service = google_compute_backend_service.keycloak.id
    }

    path_rule {
      paths   = ["/admin/*"]
      service = google_compute_backend_service.keycloak.id
    }

    path_rule {
      paths   = ["/resources/*"]
      service = google_compute_backend_service.keycloak.id
    }

    path_rule {
      paths   = ["/js/*"]
      service = google_compute_backend_service.keycloak.id
    }
  }
}

# ---------------------------------------------------------------------------
# HTTPS Proxy + Forwarding Rule
# ---------------------------------------------------------------------------

resource "google_compute_target_https_proxy" "main" {
  name             = "deepsecure-https-proxy"
  project          = var.project_id
  url_map          = google_compute_url_map.main.id
  ssl_certificates = [google_compute_managed_ssl_certificate.main.id]
}

resource "google_compute_global_forwarding_rule" "https" {
  name                  = "deepsecure-https-rule"
  project               = var.project_id
  ip_address            = google_compute_global_address.lb.address
  ip_protocol           = "TCP"
  port_range            = "443"
  target                = google_compute_target_https_proxy.main.id
  load_balancing_scheme = "EXTERNAL_MANAGED"
}
