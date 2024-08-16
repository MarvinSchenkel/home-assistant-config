# Marvin's Home Assistant Configuration
[![GitHub Actions][actions-shield]][actions]
[![GitHub Activity][commits-shield]][commits]
[![GitHub Last Commit][last-commit-shield]][commits]

![GitHub Stars][stars-shield]
![GitHub Watchers][watchers-shield]
![GitHub Forks][forks-shield]

Hey there 👋!
This is my personal home assistant configuration. My modular setup is based on Frenck's configuration found [here](https://github.com/frenck/home-assistant-config). The aim of my setup is to automate as many things as possible, reducing the need for a mobile app to control my house. However, it does include a beautiful for those few cases where I want to take control.

Feel free to have a look at my automations and draw some inspiration from them. Happy home automating :house:!

## Features
Some of the highlights of my setup include:
- 📻 **Personal DJ**: As a core member of the [Music Assistant](https://music-assistant.io/) I obviously had to apply it to my smart home. I use a combination of a [music schedule](./automations/house/music_schedule.yaml) that changes based on the time of day along with some base playlists that I use to [dynamically populate my queue](https://github.com/MarvinSchenkel/home-assistant-config/blob/master/automations/house/populate_music_queue.yaml). This gives me an endless stream of music that matches the time of day _and_ it allows me to discover new music.
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

## Tips / Design principles
My smart home is based on a few core principles that ensures maximum flexability along with great stability (you know, to keep the wife happy 😉).

### 👆 An automation should control 1 thing in 1 area
I have tried *many* different approaches to writing automations. Often this quickly became messy as multiple automations would control the same device, resulting in unwanted behaviour in my home. The method that works best for me is to create a single automation that controls a 'thing' within an area. For example, there is [1 automation that controls my lights in my living room](./automations/areas/livingroom/lights.yaml). This automation contains every single `trigger` that might impact whether I want to make changes to the lights and uses a [`choose`](https://www.home-assistant.io/docs/scripts/#choose-a-group-of-actions) to handle the different scenarios. Bonus tip: Entities used in your conditions should also be included in your triggers. This ensures your 'thing' is always up to date with your logic.

### 👆 Use template entities to abstract concepts in your smart home
Template entities are amazing. They allow you to centralize logic in one place and re-use it across many different automations. For example, I have created a binary sensor [`presence_livingroom`](./entities/templates/binary_sensors/presence/presence_livingroom.yaml) that checks multiple things that could indicate presence in that room. It checks whether some doors have opened and whether some sensor have detected presence. This results in a single, reusable `binary_sensor` for the concept of 'presence in the living room', which can be used in your automations. This principle really shines when you change a sensor in a room or quickly want to change the definition of a 'concept': you only have to change it in one place, no updates to automations are required. Still need more inspiration? All 'concept' I have created can be found [here](./entities/templates/).

## My setup
### Infrastructure
| Product | Description |
| -- | -- |
| Intel NUC i7 kit NUC10i7FNH | I am running HassOS on an Intel NUC using Proxmox |
| Raspberry Pi 3B+ and Aeotec Z-Wave stick | This is my Z-Wave component that runs Zwave-JS and connects to Home Assistant using websockets |
| Sonoff Zigbee Bridge | I flashed the Zigbee bridge with [Tasmota](https://www.digiblur.com/2020/07/how-to-use-sonoff-zigbee-bridge-with.html) and use it as a Zigbee bridge |
| Ubiquity Unifi | I used several Unifi products (router, switches and AP's) to built my home network.

[commits-shield]: https://img.shields.io/github/commit-activity/y/MarvinSchenkel/home-assistant-config.svg
[commits]: https://github.com/MarvinSchenkel/home-assistant-config/commits/master
[last-commit-shield]: https://img.shields.io/github/last-commit/MarvinSchenkel/home-assistant-config.svg
[stars-shield]: https://img.shields.io/github/stars/MarvinSchenkel/home-assistant-config.svg?style=social&label=Stars
[forks-shield]: https://img.shields.io/github/forks/MarvinSchenkel/home-assistant-config.svg?style=social&label=Forks
[watchers-shield]: https://img.shields.io/github/watchers/MarvinSchenkel/home-assistant-config.svg?style=social&label=Watchers
[actions-shield]: https://github.com/MarvinSchenkel/home-assistant-config/workflows/Home%20Assistant%20CI/badge.svg
[actions]: https://github.com/MarvinSchenkel/home-assistant-config/actions