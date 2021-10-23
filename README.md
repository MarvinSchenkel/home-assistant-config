# Marvin's Home Assistant Configuration
[![GitHub Activity][commits-shield]][commits]
[![GitHub Last Commit][last-commit-shield]][commits]

![GitHub Stars][stars-shield]
![GitHub Watchers][watchers-shield]
![GitHub Forks][forks-shield]

Hey there 👋!
This is my personal home assistant configuration. My modular setup is based on Frenck's configuration found [here](https://github.com/frenck/home-assistant-config). Feel free to have a look at my automations and draw some inspiration from them. Happy home automating :house:! 

## Features
Some of the highlights of my setup include:
- 🎶 **Follow-me music**: My music automatically follows me around the house whenever music is playing in the living room. I use [Sonos](https://www.sonos.com) speakers all throughout my house in combination with motion sensors to achieve this. Have a look at [this](./blueprints/automation/motion_group_sonos.yaml) blueprint for more information.
- :sunny: : **Automatic sun protection**. My blinds automatically close on hot days whenever the sun is shining directly on the south-facing windows. I use my solar panels to measure the sun's intensity and use the sun's azimuth/elevation to determine whether it is shining directly on my windows. Have a look at [these](./entities/templates/binary_sensors/sun) entities if you want to learn more.
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
- 💡 **Advanced lighting**: My lights automatically adjust to the sun's state by using the [adaptive_lighting](https://github.com/basnijholt/adaptive-lighting) component. I combine this with advanced presence detection and manual override logic to be able to flexibly control our lights when we want to, but automate them in any other case.
- **Dashboard**: My dashboard is based on the awesome work of Mattias. He built an amazing responsive dashboard that I customized and use as my mobile app. Here's a preview:
![screenshot](https://raw.githubusercontent.com/MarvinSchenkel/home-assistant-config/master/www/img/dashboard.png)
TODO: Convice the wife we actually need a wall-mounted tablet

## Design principles
TODO

## My setup
TODO

[commits-shield]: https://img.shields.io/github/commit-activity/y/MarvinSchenkel/home-assistant-config.svg
[commits]: https://github.com/MarvinSchenkel/home-assistant-config/commits/master
[last-commit-shield]: https://img.shields.io/github/last-commit/MarvinSchenkel/home-assistant-config.svg
[stars-shield]: https://img.shields.io/github/stars/MarvinSchenkel/home-assistant-config.svg?style=social&label=Stars
[forks-shield]: https://img.shields.io/github/forks/MarvinSchenkel/home-assistant-config.svg?style=social&label=Forks
[watchers-shield]: https://img.shields.io/github/watchers/MarvinSchenkel/home-assistant-config.svg?style=social&label=Watchers