package aegis.policy.allow

default allow = false

# By default, non-navigate actions are permitted.
allow {
    input.action != "navigate"
}

# Allow navigation only to sanctioned domains.
allow {
    input.action == "navigate"
    allowed_domains := [
        "jobs.our-company.com", 
        "internal.our-company.com",
        "www.linkedin.com"
    ]
    some i
    endswith(input.url, allowed_domains[i])
}