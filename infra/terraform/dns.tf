# ---------------------------------------------------------------------------
# Cloud DNS — OPTIONAL
# ---------------------------------------------------------------------------
# Uncomment the resources below if your domain's DNS is managed by
# Google Cloud DNS.  Otherwise, create an A record manually at your
# DNS provider pointing to the load-balancer IP:
#
#   Host: app          (or @ for apex)
#   Type: A
#   Value: <output.lb_ip_address>
#   TTL:  300
#
# After applying Terraform, retrieve the IP with:
#   terraform output lb_ip_address
# ---------------------------------------------------------------------------

# resource "google_dns_managed_zone" "main" {
#   name     = "deepsecure-zone"
#   dns_name = "deepsecure.io."
#   project  = var.project_id
# }

# resource "google_dns_record_set" "app" {
#   name         = "app.deepsecure.io."
#   type         = "A"
#   ttl          = 300
#   managed_zone = google_dns_managed_zone.main.name
#   project      = var.project_id
#   rrdatas      = [google_compute_global_address.lb.address]
# }
