# Snapshot module variables — Phase 0.

variable "lab_id" {
  type = string
}
variable "node_id" {
  type = string
}
variable "snapshot_name" {
  type = string
}
variable "source_disk_self_link" {
  type = string
}
variable "zone" {
  type    = string
  default = "europe-west3-a"
}
variable "project_id" {
  type = string
}
variable "labels" {
  type    = map(string)
  default = {}
}
