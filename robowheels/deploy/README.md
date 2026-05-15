# RoboWheels deploy (GitHub Actions + MEATBALL runner)

Repository: [roboRob](https://github.com/JamesRodgers-git/roboRob) (monorepo; only `robowheels/` is deployed by this workflow).

Deploys only the `robowheels/` tree to the Pi Zero 2 W motion controller. **robobrain** is deployed separately on another Pi later.

## After renaming the GitHub repository

- **Workflows and secrets** stay on the same repo; no workflow edits are required (`actions/checkout` uses the current repository automatically).
- **Local clones:** `git remote set-url origin https://github.com/JamesRodgers-git/roboRob.git`
- **Self-hosted runner (MEATBALL):** Usually keeps working after a GitHub rename. If jobs stop picking up, remove and re-register the runner from **Settings → Actions → Runners** on the renamed repo, or re-run the runner install script so its config points at `JamesRodgers-git/roboRob`.

## Architecture

1. Push to `main` (under `robowheels/` or this workflow file).
2. **ubuntu-latest** job runs unit tests.
3. **self-hosted runner `MEATBALL`** rsyncs `robowheels/` → `~/robowheels/` on the Pi.
4. SSH runs `deploy/bootstrap-remote.sh` (apt, I2C/UART, USB gadget boot lines, venv, systemd).

## One-time: GitHub runner (desktop)

1. On the always-on desktop (WSL2 Ubuntu recommended on Windows), register a self-hosted runner from the repo **Settings → Actions → Runners → New self-hosted runner**.
2. When configuring labels, include **`MEATBALL`** (in addition to `self-hosted`).
3. Install the runner as a **service** so it runs when you are not logged in.
4. Ensure `ssh` and `rsync` work from that same environment to the Pi.
5. **Windows runners (MEATBALL):**
   - Install **[Git for Windows](https://git-scm.com/download/win)** (includes Git Bash; enable optional **Unix tools** / rsync in setup).
   - The workflow uses the no-space short path `C:\PROGRA~1\Git\bin\bash.exe` explicitly — **not** WSL. If you see `WSL has no installed distributions`, your runner was using WSL bash; reinstall Git for Windows or register the runner inside WSL Ubuntu instead.
   - Deploy key file: `%USERPROFILE%\.ssh\robowheels_deploy` (not `webfactory/ssh-agent`).
   - The workflow does not write local filesystem paths to `GITHUB_ENV`; each Git Bash step re-derives `~/.ssh` paths from the runner environment to avoid Windows drive-letter parsing errors.

## One-time: Pi after wipe

Before the first successful workflow run:

1. Flash Raspberry Pi OS, set hostname (e.g. `robowheels`).
2. Create user (e.g. `heiwashin`) and enable SSH.
3. Add the **deploy public key** to `~/.ssh/authorized_keys` for that user.
4. Optional: reserve a **DHCP static lease** and use the IP in `ROBOWHEELS_SSH_HOST` (more reliable than `.local` from WSL).

## GitHub repository secrets

| Secret | Description |
|--------|-------------|
| `ROBOWHEELS_SSH_HOST` | Pi hostname or IP, e.g. `192.168.1.42` or `robowheels.local` |
| `ROBOWHEELS_SSH_USER` | SSH user, e.g. `heiwashin` |
| `ROBOWHEELS_SSH_PRIVATE_KEY` | Private key matching the Pi `authorized_keys` entry |

Generate a deploy key:

```bash
ssh-keygen -t ed25519 -f robowheels-deploy -N ""
# Add robowheels-deploy.pub to the Pi; store robowheels-deploy contents in the secret.
```

## Verify on the Pi

```bash
systemctl status robowheels-drive
journalctl -u robowheels-drive -f
ls /dev/ttyGS*    # USB gadget serial (after reboot if boot config changed)
i2cdetect -y 1    # motor DACs (after I2C enabled)
```

## Manual bootstrap (without Actions)

```bash
rsync -az --delete --exclude .venv ./robowheels/ heiwashin@robowheels.local:~/robowheels/
ssh heiwashin@robowheels.local 'bash ~/robowheels/deploy/bootstrap-remote.sh'
```

## Boot config changes

If bootstrap adds USB gadget lines to `/boot/firmware/config.txt` or `cmdline.txt`, **reboot the Pi once** before expecting `/dev/ttyGS*`. Set `REBOOT_IF_BOOT_CHANGED=true` on the SSH step to auto-reboot (optional).

## Service

- Unit: `robowheels-drive.service`
- Runs: `~/robowheels/.venv/bin/python drive.py`
- User: deploy user with supplementary groups `gpio`, `i2c`, `dialout`
