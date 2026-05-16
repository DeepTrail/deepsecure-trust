resource "google_vpc_access_connector" "serverless" {
  name          = "deepsecure-vpc-cx"
  region        = var.region
  network       = "default"
  ip_cidr_range = "10.8.0.0/28"
  machine_type  = "e2-micro"
  min_instances = 2
  max_instances = 3

  depends_on = [google_project_service.apis["vpcaccess.googleapis.com"]]
}
