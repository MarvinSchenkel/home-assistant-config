# Marvin's Home Assistant Configuration
[![GitHub Activity][commits-shield]][commits]
[![GitHub Last Commit][last-commit-shield]][commits]

![GitHub Stars][stars-shield]
![GitHub Watchers][watchers-shield]
![GitHub Forks][forks-shield]

Hey there 👋!
This is my personal home assistant configuration. My modular setup is based on Frenck's configuration found [here](https://github.com/frenck/home-assistant-config). The aim of my setup is to automate as many things as possible, reducing the need for a mobile app to control my house. However, it does include a beautiful dashboard / mobile app (inspired by [Mattias](https://github.com/matt8707/hass-config)) for those few cases where I want to take control. 

Feel free to have a look at my automations and draw some inspiration from them. Happy home automating :house:! 

## Features
Some of the highlights of my setup include:
- 🎶 **Follow-me music**: My music automatically follows me around the house whenever music is playing in the living room. I use [Sonos](https://www.sonos.com) speakers all throughout my house in combination with motion sensors to achieve this. Have a look at [this](./blueprints/automation/motion_group_sonos.yaml) blueprint for more information.
- :sunny: **Automatic sun protection**: My blinds automatically close on hot days whenever the sun is shining directly on the south-facing windows. I use my solar panels to measure the sun's intensity and use the sun's azimuth/elevation to determine whether it is shining directly on my windows. Have a look at [these](./entities/templates/binary_sensors/sun) entities if you want to learn more.
- :busts_in_silhouette: **Advanced presence detection**: I use [various automations](./automations/presence) to build an advance presence detection system that keeps track of different presence states:
    - Just home
    - Home
    - Just away
    - Away
    - Away long
    - Asleep
    - Just awake
    - Awake

  This setup is inspired by [Phil Hawthorne's excellent blog](https://philhawthorne.com/making-home-assistants-presence-detection-not-so-binary/). I use these different states to trigger various automations, for example [start a morning playlist](./automations/areas/bathroom/play_music.yaml) whenever we have just woken up.
- 📢 **Notification system**: I use a [custom script](./scripts/send_notification.yaml) that determines whether to send us a push notification, a pop-up on the TV, an announcement on our speakers or a combination of the three.
- 💡 **Advanced lighting**: My lights automatically adjust to the sun's state by using different scenes. I combine this with advanced presence detection and manual override logic to be able to flexibly control our lights when we want to, but automate them in any other case.
- 📟 **Dashboard**: My dashboard is based on the awesome work of [Mattias](https://github.com/matt8707/hass-config). He built an amazing responsive dashboard that I customized and use as my mobile app. Here's a preview:

![screenshot](https://raw.githubusercontent.com/MarvinSchenkel/home-assistant-config/master/www/img/dashboard.png)
TODO: Convice the wife we actually need a wall-mounted tablet.

## Tips / Design principles
TODO

## My setup
### Infrastructure
| Product | Description |
| -- | -- |
| Intel NUC i7 kit NUC10i7FNH | I am running HassOS on an Intel NUC using Proxmox |
| Raspberry Pi 3B+ and Aeotec Z-Wave stick | This is my Z-Wave component that runs Zwave-JS and connects to Home Assistant using websockets |
| Sonoff Zigbee Bridge | I flashed the Zigbee bridge with [Tasmota](https://www.digiblur.com/2020/07/how-to-use-sonoff-zigbee-bridge-with.html) and use it as a Zigbee bridge. |
| Ubiquity Unifi | I used several Unifi products (router, switches and AP's) to built my home network. I [configured several VLANs](https://www.youtube.com/watch?v=vz3u6E3Fxi8) to separate our private devices from IoT devices for security purposes |

[commits-shield]: https://img.shields.io/github/commit-activity/y/MarvinSchenkel/home-assistant-config.svg
[commits]: https://github.com/MarvinSchenkel/home-assistant-config/commits/master
[last-commit-shield]: https://img.shields.io/github/last-commit/MarvinSchenkel/home-assistant-config.svg
[stars-shield]: https://img.shields.io/github/stars/MarvinSchenkel/home-assistant-config.svg?style=social&label=Stars
[forks-shield]: https://img.shields.io/github/forks/MarvinSchenkel/home-assistant-config.svg?style=social&label=Forks
[watchers-shield]: https://img.shields.io/github/watchers/MarvinSchenkel/home-assistant-config.svg?style=social&label=Watchers