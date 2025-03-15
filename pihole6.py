#!/usr/bin/env python3

# A straight-up ChatGPT conversion of the pihole6.php
# CheckMK local check by halfordfan et al.

import requests
import time
import json

# Load credentials from the JSON file
with open('credentials.json', 'r') as file:
    credentials = json.load(file)

MP = credentials.get('MP')
base_url = credentials.get('base_url')
sid = ""

if 'MP' in globals():
    auth_url = f"{base_url}/auth"
    payload = {"password": MP}
    headers = {
        'Content-Type': 'application/json',
        'accept': 'application/json'
    }

    response = requests.post(auth_url, json=payload, headers=headers)
    result = response.json()

    if not result.get('session', {}).get('valid', False):
        raise SystemExit("Failed to contact Pi-Hole API endpoint. Aborting!")

    sid = f"?sid={result['session']['sid']}"

# Get Pi-hole blocking status
status_url = f"{base_url}/dns/blocking{sid}"
response = requests.get(status_url)
if not response.ok:
    raise SystemExit("API returned no data! Check password and access lists!")

status_data = response.json()
if status_data.get("blocking") == "enabled":
    print('0 "Pi-Hole Status" enabled=1 Pi-Hole ad blocking is enabled')
else:
    print('1 "Pi-Hole Status" enabled=0 Pi-Hole ad blocking is disabled')

# Get Pi-hole DHCP status
dhcp_status_url = f"{base_url}/config/dhcp{sid}"
response = requests.get(dhcp_status_url)
if not response.ok:
    raise SystemExit("API returned no data! Check password and access lists!")

dhcp_status_data = response.json()

# Check if DHCP is active
dhcp_active = 1 if dhcp_status_data["config"]["dhcp"]["active"] else 0

# Extract DHCP info
start = dhcp_status_data["config"]["dhcp"]["start"]
end = dhcp_status_data["config"]["dhcp"]["end"]
router = dhcp_status_data["config"]["dhcp"]["router"]

# Extract lease time
lease_time = dhcp_status_data["config"]["dhcp"]["leaseTime"]

# Count the number of hosts
hosts_count = len(dhcp_status_data["config"]["dhcp"]["hosts"])

# Get Pi-hole DHCP leases
dhcp_leases_url = f"{base_url}/dhcp/leases{sid}"
response = requests.get(dhcp_leases_url)
if not response.ok:
    raise SystemExit("API returned no data! Check password and access lists!")

dhcp_leases_data = response.json()

# Count the number of DHCP leases
leases_count = len(dhcp_leases_data["leases"])

# Convert lease time to seconds if it is in minutes or hours
if lease_time.endswith('m'):
    lease_time_seconds = int(lease_time[:-1]) * 60
elif lease_time.endswith('h'):
    lease_time_seconds = int(lease_time[:-1]) * 3600
else:
    lease_time_seconds = lease_time

# Determine the status code based on dhcp_active
status_code = 0 if dhcp_active == 1 else 2

# Print the combined DHCP status with lease time in seconds
print(f'{status_code} "Pi-Hole DHCP Status" enabled={dhcp_active}|lease_time={lease_time_seconds}|hosts_count={hosts_count}|leases_count={leases_count} start={start} end={end} router={router} lease_time={lease_time_seconds}s hosts_count={hosts_count} leases_count={leases_count} Pi-Hole DHCP Status: Enabled={dhcp_active}, Start={start}, End={end}, Router={router}, Lease Time={lease_time_seconds}s, Hosts Count={hosts_count}, Leases Count={leases_count}')
# Get Pi-hole summary stats
summary_url = f"{base_url}/stats/summary{sid}"
response = requests.get(summary_url)
summary_data = response.json()

if "queries" not in summary_data:
    raise SystemExit("Failed to contact Pi-Hole API endpoint. Aborting!")

metrics = {
    'total_queries': f'total_queries={summary_data["queries"]["total"]}',
    'blocked_queries': f'blocked_queries={summary_data["queries"]["blocked"]}',
    'percent_blocked': f'percent_blocked={round(summary_data["queries"]["percent_blocked"], 1)}',
    'domains_being_blocked': f'domains_being_blocked={summary_data["gravity"]["domains_being_blocked"]}',
    'cached_queries': f'cached_queries={summary_data["queries"]["cached"]}',
    'forwarded_queries': f'forwarded_queries={summary_data["queries"]["forwarded"]}',
    'frequency': f'frequency={round(summary_data["queries"]["frequency"], 1)}',
    'clients': f'clients={summary_data["clients"]["total"]}'
}
print(f'0 "Pi-Hole Summary" {"|".join(metrics.values())} Pi-Hole Statistics Summary {", ".join(metrics.values()).replace("=",": ")}')

# Check last gravity update
last_gravity = int(time.time()) - summary_data["gravity"]["last_update"]
days_old = int(round(last_gravity / 86400, 0))

# Convert thresholds from days to seconds
warning_threshold = 8 * 86400  # 8 days in seconds
critical_threshold = 15 * 86400  # 15 days in seconds

print(f'P "Pi-Hole Gravity" gravity_age={last_gravity};{warning_threshold};{critical_threshold} Pi-Hole Gravity lists were updated ', end='')

if last_gravity < 60:
    time_value, unit = last_gravity, "second"
elif 60 <= last_gravity < 3600:
    time_value, unit = int(round(last_gravity / 60, 0)), "minute"
elif 3600 <= last_gravity < 86400:
    time_value, unit = int(round(last_gravity / 3600, 0)), "hour"
else:
    time_value, unit = days_old, "day"

print(f"{time_value} {unit}{'s' if time_value != 1 else ''} ago")

# Check for Pi-hole updates
update = 0
message = "Pi-Hole is up to date "
updates_url = f"{base_url}/info/version{sid}"
response = requests.get(updates_url)
updates_data = response.json()
metrics = []

for key in ["core", "web", "ftl"]:
    if updates_data["version"][key]["local"]["hash"] != updates_data["version"][key]["remote"]["hash"]:
        metrics.append(f"{key}=1")
        update = 1
        message = "Pi-Hole update available (run 'pihole -up'), "
    else:
        metrics.append(f"{key}=0")

print(f'{update} "Pi-Hole Update" {"|".join(metrics)} {message}({", ".join(metrics).replace("=", ": ").replace("0", "current").replace("1", "update needed")})')

# Logout if authenticated
if 'MP' in globals():
    logout_url = f"{auth_url}{sid}"
    requests.delete(logout_url, headers={'accept': 'application/json'})