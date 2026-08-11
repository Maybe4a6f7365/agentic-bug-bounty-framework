variable "lab_id" {
  type = string
}

variable "network_self_link" {
  type        = string
  description = "Self-link of the isolated lab VPC."
}

variable "target_tags" {
  type = list(string)
}

variable "egress_destination_ranges" {
  type    = list(string)
  default = ["199.36.153.4/30"]
}

variable "egress_protocol" {
  type    = string
  default = "tcp"
}

variable "egress_ports" {
  type    = list(string)
  default = ["443"]
}
