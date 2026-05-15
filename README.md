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

<div style="padding:75% 0 0 0;position:relative;">
  <iframe src="https://player.vimeo.com/video/1192709597?badge=0&amp;autopause=0&amp;player_id=0&amp;app_id=58479" frameborder="0" allow="autoplay; fullscreen; picture-in-picture; clipboard-write; encrypted-media; web-share" referrerpolicy="strict-origin-when-cross-origin" style="position:absolute;top:0;left:0;width:100%;height:100%;" title="RoboWheels remote-control drive demo"></iframe>
</div>

[Watch the remote-control drive demo on Vimeo](https://vimeo.com/1192709597)

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

