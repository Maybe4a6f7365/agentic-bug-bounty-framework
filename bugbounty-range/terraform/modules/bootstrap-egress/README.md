# WordPress Bootstrap Egress

Creates one persistent priority-1000 EGRESS firewall rule for HTTPS access to
the restricted Google APIs VIP range `199.36.153.4/30`. It applies only to
`target_tags` and persists until Lab-Destroy. The module never creates NAT,
public IPs, or general Internet egress.
