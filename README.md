# roboRob

Robotics stack for a dual-Pi setup:

| Directory | Hardware | Role |
|-----------|----------|------|
| [robowheels/](robowheels/) | Raspberry Pi Zero 2 W | Motion: CRSF radio, motors, brakes, USB gadget AI serial |
| [robobrain/](robobrain/) | Raspberry Pi 5 + AI HAT+ | Perception and AI movement commands to robowheels |

## Clone

```bash
git clone https://github.com/JamesRodgers-git/roboRob.git
cd roboRob
```

## Deploy (robowheels)

CI deploys `robowheels/` to the motion Pi via the self-hosted runner **MEATBALL**. See [robowheels/deploy/README.md](robowheels/deploy/README.md).

## Local remote after a GitHub rename

If the repository was renamed on GitHub, update your local clone:

```bash
git remote set-url origin https://github.com/JamesRodgers-git/roboRob.git
```

GitHub redirects the old `codex` URL for a while; updating `origin` avoids surprises later.
