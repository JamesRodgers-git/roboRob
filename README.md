# roboRob

Robotics stack for a dual-Pi setup:

## RoboWheels in action

<table>
  <tr>
    <td width="50%">
      <img src="assets/PXL_20260515_193718843.jpg" alt="RoboWheels electronics and wiring on the chassis" />
    </td>
    <td width="50%">
      <img src="assets/img-20260515-145347-d0-P0-0.jpg" alt="RoboWheels driving outside under remote control" />
    </td>
  </tr>
  <tr>
    <td align="center"><strong>Electronics bay</strong></td>
    <td align="center"><strong>Outdoor drive test</strong></td>
  </tr>
</table>

<video src="assets/vid-20260515-151634-f8.mp4" controls width="100%" title="RoboWheels remote-control drive demo"></video>

[Watch the remote-control drive demo](assets/vid-20260515-151634-f8.mp4)

## Project layout

| Directory | Hardware | Role |
|-----------|----------|------|
| [robowheels/](robowheels/) | Raspberry Pi Zero 2 W | Motion: CRSF radio, motors, brakes, USB gadget AI serial |
| [robobrain/](robobrain/) | Raspberry Pi 5 + AI HAT+ | Perception and AI movement commands to robowheels |

## Clone

```bash
git clone https://github.com/JamesRodgers-git/roboRob.git
cd roboRob
```

