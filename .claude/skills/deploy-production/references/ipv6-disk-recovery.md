# IPv6 & Disk Recovery Reference

> **Scope:** Supabase logical replication over Docker IPv6, and disk-full crash recovery.
> Loaded when: replication errors, `Network unreachable`, `No space left on device`, or slot corruption.

## Supabase Has No IPv4

`db.<project>.supabase.co` resolves **only** to an AAAA (IPv6) record. There is no A record. This means:

- `/etc/hosts` IPv4 workaround → **impossible** (no IPv4 to point to)
- `dnsmasq` IPv4 forwarding → **impossible** (no IPv4 upstream)
- Docker IPv6 → **mandatory** for any container-to-Supabase connection

## Enabling Docker IPv6

### Prerequisites

1. Host must have a global IPv6 address (`ip -6 addr show scope global`)
2. Host must have IPv6 default route (`ip -6 route show default`)
3. IPv6 forwarding must be enabled

### Step 1: Daemon config

```bash
sudo tee /etc/docker/daemon.json > /dev/null << 'EOF'
{
  "ipv6": true,
  "fixed-cidr-v6": "fd00::/80",
  "ip6tables": true
}
EOF
```

### Step 2: Enable forwarding

```bash
sudo sysctl -w net.ipv6.conf.all.forwarding=1
sudo sysctl -w net.ipv6.conf.default.forwarding=1
# Persist:
echo 'net.ipv6.conf.all.forwarding=1' | sudo tee -a /etc/sysctl.conf
echo 'net.ipv6.conf.default.forwarding=1' | sudo tee -a /etc/sysctl.conf
```

### Step 3: Compose network config

**Both** compose files (`docker-compose.production.yml` and `docker-compose.production-pg.yml`) must declare IPv6 on the `default` network with the **same subnet**. If they differ, Docker tries to recreate the network and fails with `has active endpoints`.

```yaml
networks:
  default:
    enable_ipv6: true
    ipam:
      config:
        - subnet: fd00:1::/80
```

### Step 4: Recreate networks

Existing networks don't inherit daemon.json IPv6 settings. Must recreate:

```bash
# Stop all → remove old networks → start PG first → start app
docker compose -f docker-compose.production.yml stop
docker compose -f docker-compose.production-pg.yml stop
docker compose -f docker-compose.production.yml rm -f
docker compose -f docker-compose.production-pg.yml rm -f
docker network rm <project>_default
docker compose -f docker-compose.production-pg.yml up -d   # creates network with IPv6
docker compose -f docker-compose.production.yml up -d       # joins existing network
```

> **Order matters:** PG compose must create the network first. App compose joins it. If app runs first with a different subnet config → conflict.

### Verification

```bash
# 1. Network has IPv6
docker network inspect <network> --format '{{.EnableIPv6}}'  # → true
docker network inspect <network> --format '{{json .IPAM.Config}}'  # shows both IPv4 + IPv6

# 2. Container can reach Supabase (TCP, not ICMP — ICMPv6 may be filtered)
docker exec numina-postgres-prod psql \
  'host=db.vywwletyvrzyoozhsfqu.supabase.co port=5432 user=postgres password=... dbname=postgres sslmode=require connect_timeout=10' \
  -c 'SELECT 1;'

# 3. ping6 is unreliable — ICMPv6 may be filtered even when TCP works
#    Always test with actual TCP connection (psql or Python socket), not ping
```

## Disk-Full Crash Recovery

### Symptoms

```
PANIC: could not write to file "pg_logical/replorigin_checkpoint.tmp": No space left on device
checkpointer process was terminated by signal 6: Aborted
all server processes terminated; reinitializing
```

PG enters a crash loop: recovery → PANIC → crash → restart → repeat.

### Recovery

1. **Free disk space** (the root cause):
   ```bash
   sudo docker image prune -af                                    # dangling images
   sudo docker image prune -af --filter "until=48h"               # old unused images
   df -h / | tail -1                                              # verify >15% free
   ```
2. PG auto-recovers once space is available. Wait for: `database system is ready to accept connections`

### Replication Slot Corruption

Disk-full crashes corrupt Supabase replication slots. After recovery:

```
ERROR: could not start WAL streaming: ERROR: can no longer get changes from replication slot "xxx_cdc_slot"
```

**Diagnosis:** Check slots on Supabase:
```bash
psql 'host=db...supabase.co ...' -c \
  "SELECT slot_name, active, restart_lsn FROM pg_replication_slots WHERE slot_name LIKE '%cdc%';"
```

- `restart_lsn` empty → slot data lost, must recreate
- `active = f` → slot exists but no one is connected

**Fix: Drop and recreate slots on Supabase:**

```bash
# 1. Disable local subscriptions first
psql -d numina_prod -c 'ALTER SUBSCRIPTION numina_sub DISABLE;'
psql -d numina_prod_deerflow -c 'ALTER SUBSCRIPTION deerflow_sub DISABLE;'

# 2. Drop old slots on Supabase
psql 'host=...supabase.co ... dbname=postgres' -c "SELECT pg_drop_replication_slot('numina_cdc_slot');"
psql 'host=...supabase.co ... dbname=numina_deerflow' -c "SELECT pg_drop_replication_slot('deerflow_cdc_slot');"

# 3. Create new slots on Supabase
psql 'host=...supabase.co ... dbname=postgres' -c "SELECT pg_create_logical_replication_slot('numina_cdc_slot', 'pgoutput');"
psql 'host=...supabase.co ... dbname=numina_deerflow' -c "SELECT pg_create_logical_replication_slot('deerflow_cdc_slot', 'pgoutput');"

# 4. Re-enable local subscriptions
psql -d numina_prod -c 'ALTER SUBSCRIPTION numina_sub ENABLE;'
psql -d numina_prod_deerflow -c 'ALTER SUBSCRIPTION deerflow_sub ENABLE;'

# 5. Verify: slots should show active=t, confirmed_flush_lsn advancing
```

## Prevention

| Risk | Prevention |
|------|-----------|
| Disk full | Monitor `df -h /` >85%. Regular `docker image prune`. Alert threshold: <2GB free |
| Slot corruption | Keep disk >20% free. WAL accumulation is the #1 disk consumer during heavy writes |
| IPv6 breakage | After Docker upgrades or daemon.json changes, verify `docker network inspect` shows `EnableIPv6=true` |
| Silent replication lag | Check `confirmed_flush_lsn` periodically — if it stops advancing, the slot is stuck |
