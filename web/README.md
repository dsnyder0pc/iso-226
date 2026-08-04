# Equal-loudness filter API

A read-only HTTP service that returns parametric-EQ filter sets for a measured
listening level. It is a lookup over a precomputed grid — no fitting happens at
request time.

## Why it is built this way

Fitting one preset takes 20–45 s (constrained minimax, multistart), which is
far too slow for an HTTP request and would pin a worker for the better part of
a minute. It does not need to happen online: the compensation curve depends on
`level - reference`, not on the two levels separately, so the parameter space
collapses to a single offset axis. `precompute_presets.py` fits that grid once
on a development machine and writes `presets.json`.

The consequence is that **this service needs neither NumPy nor SciPy**. It is
Flask plus a JSON file, which is what makes it comfortable on a 1 GB / 1 vCPU
droplet.

## Endpoints

```
GET /v1/filters?level=65[&reference=83]
GET /v1/meta      what the service can serve
GET /health       liveness
```

`level` is required — the *measured* listening level in dB SPL, broadband,
C-weighted, slow. `reference` is a property of the recording and defaults to
83 dB. Unknown query parameters are ignored.

`scale` (partial compensation) is not served in v1. A request for any scale
other than full compensation is rejected rather than silently answered with a
different curve; run `precompute_presets.py --all-scales` and redeploy
`presets.json` to enable it.

### Response shape

Every response — success, client error, server error — has the same two
top-level keys, so a consumer can parse one shape:

```json
{
  "status": {
    "ok": true,
    "request":  {"level": 65.0, "reference": 83.0},
    "resolved": {"offset_db": -18, "scale": 1.0},
    "preset":   {"band_count": 5, "design_fs": 44100,
                 "headroom_db": -9.4, "max_residual_db": 0.0925,
                 "target_met": false},
    "source":   {"api_version": "1", "iso_edition": "ISO 226:2023",
                 "generated_utc": "..."},
    "notes": []
  },
  "filters": [
    {"band": 1, "type": "Low Shelf", "frequency": 95.0, "gain": 4.59, "q": 0.38}
  ]
}
```

On error, `filters` is `[]` and `status.error` carries `code`, `message`, and
where useful `parameter` and `suggestions`.

`headroom_db` is not advisory. It is the worst-case peak across 44.1/48/96/192
kHz and must be applied as negative preamp or the cascade clips.

### Status codes

| Code | Meaning |
| :--- | :--- |
| 200 | Preset returned |
| 400 | Malformed or missing parameter (fails the numeric grammar) |
| 422 | Well-formed but unsatisfiable — out of range, offset not covered, correction exceeds the 12 dB budget |
| 404 / 405 | Unknown endpoint / wrong method — still JSON |
| 500 | Unhandled error — still JSON |

## Rebuilding the preset grid

Run on a machine with the ISO Table 1 data present (see the repository
`CONTRIBUTING.md`), not on the droplet:

```bash
python precompute_presets.py --out web/presets.json --jobs 4
python precompute_presets.py --out web/presets.json --all-scales   # 10x work
```

Then copy `presets.json` to the server and restart. The file is the only thing
that needs to change when the filter maths does.

## Deploying

```bash
sudo apt install python3-venv nginx
python3 -m venv /opt/iso226/venv
/opt/iso226/venv/bin/pip install -r requirements.txt
```

Copy `app.py` and `presets.json` to `/opt/iso226/`, then:

```ini
# /etc/systemd/system/iso226-api.service
[Unit]
Description=Equal-loudness filter API
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/iso226
Environment=PRESETS_PATH=/opt/iso226/presets.json
ExecStart=/opt/iso226/venv/bin/gunicorn --workers 2 --bind 127.0.0.1:8000 app:app
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Two workers is right for one vCPU: requests are microseconds of dictionary
lookup, so the limit is concurrency of I/O rather than CPU. Put nginx in front
for TLS, and consider a `proxy_cache` or long `Cache-Control` — the responses
are immutable for a given `presets.json`.
