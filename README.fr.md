# Muslim Reminder pour Home Assistant

[English](README.md)

[Muslim Reminder](https://muslim-reminder.com) dans toute la maison :

- les **horaires de prière** dans Home Assistant, calculés exactement comme dans l'app Muslim Reminder (même
  bibliothèque, mêmes méthodes, mêmes réglages ; vérifiés contre la bibliothèque de l'app sur 6 912 combinaisons
  jour × lieu × méthode) ;
- les **rappels de salawat** (prière sur le Prophète ﷺ) joués sur les enceintes de la maison, toutes les 5 à
  60 minutes, avec des heures de silence ;
- **l'adhan** à l'heure de chaque prière, réglable prière par prière (silencieux, court, complet) ;
- le tout **piloté par la maison** : quelqu'un est là, le bébé dort, la télé est allumée… avec des interrupteurs
  que vos automatisations commandent, ou des conditions réglées une fois pour toutes dans les options ;
- des événements, des actions et des blueprints pour tout le reste (lumières, télé, chauffage…).

Ni compte ni cloud : les horaires sont calculés sur place. Seuls les sons viennent du CDN de Muslim Reminder.

## Installation

### HACS (recommandé)

[![Ouvrir votre Home Assistant et ajouter le dépôt dans HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=muslimreminder&repository=home-assistant&category=integration)

Ou dans HACS → ⋮ → *Dépôts personnalisés* : `https://github.com/muslimreminder/home-assistant`, type *Intégration*.
Téléchargez **Muslim Reminder**, puis redémarrez Home Assistant.

### À la main

Copiez `custom_components/muslim_reminder` dans le dossier `custom_components` de votre configuration, puis redémarrez.

### Ajouter un lieu

[![Ouvrir votre Home Assistant et ajouter l'intégration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=muslim_reminder)

*Paramètres → Appareils et services → Ajouter une intégration → Muslim Reminder* :

- **Emplacement** : votre domicile par défaut ;
- **Méthode de calcul** : *Automatique* choisit la méthode du pays réglé dans Home Assistant, comme l'app
  (France → angle de France 18°, Maroc → ministère marocain, Arabie saoudite → Umm al-Qura…). Toutes les
  méthodes de l'app sont proposées ;
- **Madhab** : hanafite, ou chaféite/malékite/hanbalite (Asr standard).

On peut ajouter plusieurs lieux (une résidence secondaire, une mosquée…). *Reconfigurer* déplace un lieu.

Ouvrez ensuite **Configurer** (les options) :

| Section | Contenu |
| --- | --- |
| Enceintes | Les lecteurs multimédias des rappels de salawat, ceux de l'adhan, et *Jouer en annonce* (sur les enceintes qui le permettent — Sonos, Music Assistant, ESPHome… — la musique s'interrompt puis reprend). |
| Conditions | Les entités dont dépendent les rappels : *seulement si toutes ces entités sont actives*, *jamais tant qu'une de ces entités est active*, séparément pour les salawat et pour l'adhan. |
| Calcul | Méthode, madhab, corrections en minutes pour chaque prière, angles personnalisés : les réglages de l'app. |
| Sons | Votre propre son au lieu de ceux de l'app (une URL, ou un identifiant `media-source://` du navigateur multimédia). |

Une entité est **active** quand son état vaut `on`, `home`, `open`, `playing`, `active` ou `detected`, ou un
nombre supérieur à 0 : `zone.home` compte les personnes présentes, donc *seulement si `zone.home` est active*
veut dire « quand quelqu'un est à la maison ».

## Entités

Les identifiants suivent la langue de Home Assistant au moment de l'ajout du lieu. En français, avec un lieu
nommé *Muslim Reminder* : `sensor.muslim_reminder_fajr`, `sensor.muslim_reminder_prochaine_priere`,
`switch.muslim_reminder_rappels_de_salawat`, etc.

| Entité | |
| --- | --- |
| Fajr, Lever du soleil, Dhuhr, Asr, Maghrib, Isha (capteurs) | Les heures du jour (horodatages ; attribut `tomorrow`). Utilisables comme déclencheurs horaires. |
| Prochaine prière | L'heure de la prochaine des cinq prières (attribut `prayer`). |
| Nom de la prochaine prière | `fajr`, `dhuhr`, `asr`, `maghrib` ou `isha`. |
| Prochain rappel de salawat | L'heure du prochain rappel (inconnue quand ils sont coupés). |
| Méthode de calcul | La méthode utilisée (diagnostic). |
| Rappels de salawat (interrupteur) | Désactivé par défaut, comme dans l'app. |
| Heures de silence (interrupteur) + Début / Fin du silence | Pas de rappel entre 23 h 30 et 9 h 30 par défaut, comme dans l'app. |
| Intervalle des salawat | 5 à 60 minutes (25 par défaut). Les rappels tombent à 0 h 00 + n × intervalle. |
| Son des salawat | Les 7 sons de rappel de l'app (Choix 2 par défaut). |
| Adhan (interrupteur) | Tous les adhans. |
| Adhan de Fajr … Adhan d'Isha | Silencieux (par défaut, comme dans l'app), adhan court (30 s) ou adhan complet. |
| Muezzin | Les adhans de l'app. |
| Volume des salawat / de l'adhan | En % ; 0 laisse le volume tel quel. Hors annonce, le volume d'avant revient après le son. |
| Boutons | Jouer un rappel, jouer l'adhan, arrêter les enceintes. |
| Heure de prière, Rappel de salawat (événements) | Se déclenchent à chaque heure (type = la prière) et à chaque rappel. |

Les réglages portés par des entités sont restaurés après un redémarrage. Les sons sont aussi dans le
**navigateur multimédia** (*Médias → Muslim Reminder*), jouables sur n'importe quelle enceinte.

## Événements et actions

- `muslim_reminder_prayer` — `{prayer, time, played, config_entry_id}` à chaque heure (lever du soleil compris) ;
- `muslim_reminder_salawat` — `{played, config_entry_id}` à chaque rappel (`played` vaut false quand les
  conditions ou l'absence d'enceinte disponible l'ont laissé muet) ;
- `muslim_reminder.play_salawat` — jouer tout de suite (`entity_id`, `sound`, `volume` facultatifs) ;
- `muslim_reminder.play_adhan` — jouer tout de suite (`entity_id`, `sound`, `full`, `volume` facultatifs) ;
- `muslim_reminder.get_prayer_times` — renvoie les horaires d'un jour (`date` facultative).

Des exemples d'automatisations (télé en pause à Maghrib, salle de bain chauffée avant Fajr…) et les trois
blueprints (*À l'heure de la prière*, *Avant ou après une prière*, *Rappels de salawat quand quelqu'un est là*)
sont décrits dans le [README anglais](README.md#examples).

## Calcul des horaires

`custom_components/muslim_reminder/adhan.py` est un portage ligne à ligne d'[adhan-js](https://github.com/batoulapps/adhan-js)
4.4.3, la bibliothèque de l'app, avec les paramètres que l'app construit : la méthode (y compris celles propres
à l'app : France 12°/15°/18°, Maroc, Algérie, Tunisie, Golfe, Russie, Kemenag…), le madhab, les corrections en
minutes, les angles personnalisés et la règle *TwilightAngle* des hautes latitudes. Là où le soleil ne se lève
ou ne se couche pas (au-delà des cercles polaires), on prend les horaires de la latitude la plus proche où il le fait.

## Licence

MIT. Les sons ne font pas partie de ce dépôt.
