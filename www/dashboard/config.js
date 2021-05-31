/*
 This is an example configuration file.

 COPY OR RENAME THIS FILE TO config.js.

 Make sure you use real IDs from your HA entities.
*/

var CONFIG = {
   customTheme: null, // CUSTOM_THEMES.TRANSPARENT, CUSTOM_THEMES.MATERIAL, CUSTOM_THEMES.MOBILE, CUSTOM_THEMES.COMPACT, CUSTOM_THEMES.HOMEKIT, CUSTOM_THEMES.WINPHONE, CUSTOM_THEMES.WIN95
   transition: TRANSITIONS.ANIMATED_GPU, //ANIMATED or SIMPLE (better perfomance)
   entitySize: ENTITY_SIZES.NORMAL, //SMALL, BIG are available
   tileSize: 150,
   tileMargin: 6,
   serverUrl: 'http://' + location.hostname + ':8123',
   wsUrl: 'ws://' + location.hostname + ':8123/api/websocket',
   authToken: null, // optional long-lived token (CAUTION: only if TileBoard is not exposed to the internet)
   //googleApiKey: "XXXXXXXXXX", // Required if you are using Google Maps for device tracker
   //mapboxToken: "XXXXXXXXXX", // Required if you are using Mapbox for device tracker
   debug: false, // Prints entities and state change info to the console.
   pingConnection: true, //ping connection to prevent silent disconnections
   locale: 'nl', // locale for date and number formats - available locales: it, de, es, fr, pt, ru, nl, pl, en-gb, en-us (default). See readme on adding custom locales.
   // next fields are optional
   events: [],
   timeFormat: 24,
   menuPosition: MENU_POSITIONS.LEFT, // or BOTTOM
   hideScrollbar: false, // horizontal scrollbar
   groupsAlign: GROUP_ALIGNS.HORIZONTALLY, // or VERTICALLY
   onReady: function () {},

   header: { // https://github.com/resoai/TileBoard/wiki/Header-configuration
      styles: {
         margin: '30px 130px 0',
         fontSize: '28px'
      },
      right: [
         {
            type: HEADER_ITEMS.CUSTOM_HTML,
            html: 'Huis ter Heide'
         },
         {
            type: HEADER_ITEMS.WEATHER,
            styles: {
               margin: '0'
            },
            icon: '&weather.buienradar.state',
            state: '&weather.buienradar.state',
            icons: {
               'clear-night': 'nt-clear',
               'cloudy': 'cloudy',
               'exceptional': 'fog',
               'fog': 'fog',
               'hail': 'sleet',
               'lightning': 'chancestorms',
               'lightning-rainy': 'tstorms',
               'partlycloudy': 'partlycloudy',
               'pouring': 'rain',
               'rainy': 'chancerain',
               'snowy': 'snow',
               'snowy-rainy': 'sleet',
               'sunny': 'sunny',
               'windy': 'hazy',
               'windy-variant': 'flurries'
            },
            states: {
               'clear-night': 'Helder, nacht',
               'cloudy': 'Bewolkt',
               'exceptional': 'Exceptional',
               'fog': 'Mist',
               'hail': 'Hagel',
               'lightning': 'Onweer',
               'lightning-rainy': 'Onweer & regen',
               'partlycloudy': 'Gedeeltelijk bewolkt',
               'pouring': 'Hevige regen',
               'rainy': 'Regen',
               'snowy': 'Sneeuw',
               'snowy-rainy': 'Natte sneeuw',
               'sunny': 'Zonnig',
               'windy': 'Wind',
               'windy-variant': 'Wind'
            },
            fields: {
               temperature: '&weather.buienradar.attributes.temperature',
               temperatureUnit: '°C',
            }
          }
      ],
      left: [
         {
            type: HEADER_ITEMS.DATETIME,
            dateFormat: 'EEEE, dd LLLL', //https://docs.angularjs.org/api/ng/filter/date
         },
         // {
         //    type: HEADER_ITEMS.DATE,
         //    dateFormat: 'EEEE, LLLL dd', //https://docs.angularjs.org/api/ng/filter/date
         // },
         // {
         //    type: HEADER_ITEMS.TIME,
         // },
      ]
   },

   /*screensaver: {// optional. https://github.com/resoai/TileBoard/wiki/Screensaver-configuration
      timeout: 300, // after 5 mins of inactive
      slidesTimeout: 10, // 10s for one slide
      styles: { fontSize: '40px' },
      leftBottom: [{ type: SCREENSAVER_ITEMS.DATETIME }], // put datetime to the left-bottom of screensaver
      slides: [
         { bg: 'images/bg1.jpeg' },
         {
            bg: 'images/bg2.png',
            rightTop: [ // put text to the 2nd slide
               {
                  type: SCREENSAVER_ITEMS.CUSTOM_HTML,
                  html: 'Welcome to the <b>TileBoard</b>',
                  styles: { fontSize: '40px' }
               }
            ]
         },
         { bg: 'images/bg3.jpg' }
      ]
   },*/

   pages: [
      {
         title: 'Home',
         bg: 'images/bg1.jpeg',
         icon: 'mdi-home-outline', // home icon
         groups: [
            {
               title: 'Thuis',
               width: 2,
               height: 3,
               items: [
                  {
                     position: [0, 0],
                     width: 1,
                     map: 'yandex',
                     type: TYPES.DEVICE_TRACKER,
                     id: 'sensor.marvin_status',
                     hideEntityPicture: false,
                     slidesDelay: 2
                  },
                  {
                     position: [1, 0],
                     width: 1,
                     map: 'yandex',
                     type: TYPES.DEVICE_TRACKER,
                     id: 'sensor.laura_status',
                     hideEntityPicture: false,
                     slidesDelay: 2
                  }
               ]
            },

            {
               title: 'Woonkamer',
               width: 2,
               height: 3,
               items: [
                  {
                     width: 2,
                     position: [0, 0],
                     id: 'media_player.sonos_livingroom',
                     type: TYPES.MEDIA_PLAYER,
                     hideSource: false,
                     hideMuteButton: false,
                     state: false,
                     subtitle: '@attributes.media_title',
                     bgSuffix: '@attributes.entity_picture'
                  },
                  {
                     type: TYPES.POPUP,
                     width: 1,
                     position: [0, 1],
                     id: 'input_select.livingroom_current_scene',
                     states: {
                        'normal': 'Normaal',
                        'movie': 'Film'
                     },
                     icons: {
                        normal: 'mdi-sofa',
                        movie: 'mdi-filmstrip'
                     },
                     title: 'Licht scene',
                     popup: {
                        items: [
                           {
                              position: [0, 0],
                              id: 'scene.livingroom_normal',
                              type: TYPES.SCENE,
                              state: false,
                              title: "Normaal",
                              icon: 'mdi-sofa',
                           },
                           {
                              position: [1, 0],
                              id: 'scene.livingroom_movie',
                              type: TYPES.SCENE,
                              state: false,
                              title: "Film",
                              icon: 'mdi-filmstrip',
                           }
                        ]
                     }
                  }
               ],
            }
         ]
      },
      {
         title: 'Second page',
         bg: 'images/bg2.png',
         icon: 'mdi-numeric-2-box-outline',
         groups: [
            {
               title: '',
               width: 2,
               height: 3,
               items: [
                  {
                     position: [0, 0],
                     width: 2,
                     title: 'Short instruction',
                     type: TYPES.TEXT_LIST,
                     id: {}, // using empty object for an unknown id
                     state: false, // disable state element
                     list: [
                        {
                           title: 'Read',
                           icon: 'mdi-numeric-1-box-outline',
                           value: 'README.md'
                        },
                        {
                           title: 'Ask on forum',
                           icon: 'mdi-numeric-2-box-outline',
                           value: 'home-assistant.io'
                        },
                        {
                           title: 'Open an issue',
                           icon: 'mdi-numeric-3-box-outline',
                           value: 'github.com'
                        }
                     ]
                  },
                  {
                     position: [0, 1.5],
                     width: 1.5,
                     height: 1,
                     title: 'My Gauge Title',
                     subtitle: '',
                     type: TYPES.GAUGE,
                     id: 'sensor.pir_bathroom_temperature', // Assign the sensor you want to display on the gauge
                     value: function(item, entity) {
                        return entity.state;
                     },
                     settings: {
                        size: 200, // Defaults to 50% of either height or width, whichever is smaller
                        type: 'full', // Options are: 'full', 'semi', and 'arch'. Defaults to 'full'
                        min: 0, // Defaults to 0
                        max: 25000, // Defaults to 100
                        cap: 'round', // Options are: 'round', 'butt'. Defaults to 'butt'
                        thick: 8, // Defaults to 6
                        label: 'My Gauge', // Defaults to undefined
                        append: '@attributes.unit_of_measurement', // Defaults to undefined
                        prepend: '$', // Defaults to undefined
                        duration: 1500, // Defaults to 1500ms
                        thresholds: { 0: { color: 'green'}, 80: { color: 'red' } }, // Defaults to undefined
                        labelOnly: false, // Defaults to false
                        foregroundColor: 'rgba(0, 150, 136, 1)', // Defaults to rgba(0, 150, 136, 1)
                        backgroundColor: 'rgba(0, 0, 0, 0.1)', // Defaults to rgba(0, 0, 0, 0.1)
                        fractionSize: 0, // Number of decimal places to round the number to. Defaults to current locale formatting
                     },
                  },
               ]
            },
         ]
      }
   ],
}
