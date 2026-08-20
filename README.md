# Sonos Smart Groups

![Sonos Smart Groups](https://raw.githubusercontent.com/barloew/sonos_smart_groups/main/custom_components/sonos_smart_groups/brand/logo.png)

[![hacs][hacs-badge]][hacs-url]
[![validate][validate-badge]][validate-url]
[![release][release-badge]][release-url]

**Sonos rooms that group themselves, sound the way you meant them to, and
regroup when something more important starts playing.**

Home Assistant can group Sonos rooms. What it cannot do is remember *why* you
grouped them.

Say your kitchen opens onto the living room. The kitchen speaker sits at head
height and the living room ones are across the floor, so the kitchen needs a
little more volume and a little more bass before the two sound like one space.
When a film starts, the home theater should take the living room with it and
the kitchen should let go — then hand everything back when the film ends. And
the kid's room should switch to Night Sound once someone is asleep in it.

Those are relationships, not groups. Sonos Smart Groups is where you write them
down once, and stop thinking about them.

<!-- Add a screenshot here once you have one:
![A smart group in the blueprint editor](docs/images/blueprint.png)
-->

---

## Is this for you?

**① In a group, one Sonos room always sounds too loud, or never loud enough.**
Group the kitchen and the living room and Sonos gives them the same volume —
but the living room speaker is across an open floor and the kitchen one is at
head height. A smart group gives every follower a **volume factor**, so the
living room sits at 1.3 and stays there. Move the kitchen slider and the whole
floor follows, each room keeping its balance.

**② Your home theater and your ground-floor music want the same rooms.**
Mark the home theater as a **superior** smart group and it takes precedence
when the TV starts: the music group hands the living room over and rebuilds
itself when the film ends. No scripts, no snapshots, no room left behind in the
wrong group.

**③ Grouped rooms sound different from each other.**
Sonos keeps bass, treble, balance, loudness and the Sub settings *per room*, so
a group can still sound like several systems rather than one. A smart group
copies them across — and bass and treble get their own per-room factor, so the
room in the corner can run 0.8 and stop booming.

**④ You want music to start on its own.**
Motion in the gym, a time of day, an NFC tag by the door — a smart group can
switch to an input or start a specific playlist, album, artist or station that Home Assistant or [Music Assistant][music-assistant] can reach, at a
volume you set.

### Why not just group them in the Sonos app or using Sonos custom card via HACS?

A Sonos group is a snapshot of a decision: these speakers, right now, at one
volume. It has no memory of *why*, so every time you regroup you set the
balance again, and anything that interrupts leaves you to put it back by hand.

A smart group is the rule rather than the result. It knows which speaker leads,
how much louder each follower should be, and what should happen when something
more important comes along — so it can take itself apart and put itself back
together without you.

### Why not group them based on Home Assistant automation?

You can, and for two rooms that should always play together, a short automation is fine.

It gets harder than it looks as soon as rooms have to follow each other. You set one, it sets the other, which sets the first one back — and now they argue. Add a second group and their commands land on top of each other. Drag a volume slider and you have sent thirty commands instead of one. And the settings that make a group actually sound like one system — bass, treble, surround — cannot be reached from an automation at all.

None of that is hard to solve once. It is just tedious to solve every time. Sonos Smart Groups has solved it, so a smart group is a form you fill in and then forget about.

If you enjoy this sort of thing, the [advanced guide][advanced] explains every one of those problems and how they are handled — and the service underneath is available on its own, so you can keep writing your own automations and still get the safe writes.

### How this relates to Sonos zones, groups and pairs

Sonos has four ways to make speakers play together, and a smart group is not a
fifth — it sits on top of them.

| | What it is | Survives a reboot | Rooms keep their names |
|---|---|---|---|
| **Stereo pair** | two speakers become one room, left and right | yes | no |
| **Home theater set** | soundbar, surrounds and Sub as one room | yes | no |
| **Group** | rooms playing the same thing, right now | no | yes |
| **Zone** | two or more speakers bonded into one room | yes | no |
| **Smart group** | a rule about how rooms behave together | yes, it is a rule | yes |

**Zones** are the newest and the most often misunderstood. A zone bonds
speakers into a single room: they lose their individual names and can no longer
be addressed separately, in the Sonos app or anywhere else. Volume Trim gives
each speaker a fixed offset between −15 and +3 dB, and each keeps its own bass
and treble — but all of it is set by hand in the app, once, and never changes
by itself. Zones also rule out an Amp, any Sub, stereo pairs, soundbars and
portables, and they were built for commercial installations rather than homes.

The short version: **a zone replaces your rooms; a smart group coordinates
them.** A zone is right for eight identical speakers along one long space. A
smart group is right when the rooms should stay rooms and simply know how to
behave around each other.

They combine happily. A zone appears in Home Assistant as one player, so it can
be the leader or a follower of a smart group like anything else. The same goes
for stereo pairs and home theater sets — all of which zones exclude.

---

## Requirements

- Home Assistant **2025.7 or newer**
- Your Sonos rooms in Home Assistant, through either the
  [Sonos integration](https://www.home-assistant.io/integrations/sonos/) or
  [Music Assistant][music-assistant] — see *Using Music Assistant* below
- Sonos push updates reaching Home Assistant on **TCP port 1400**. Without them
  Home Assistant falls back to polling every 30 seconds and everything here
  feels sluggish — see *When something does not work*.

---

## Installation

### HACS (recommended)

[![Add repository to my Home Assistant][my-ha-badge]][my-ha-url]

Click the button above to open this repository in your own Home Assistant, then
click **Download**. Afterwards, **restart Home Assistant**.

Prefer to do it by hand?

1. Open **HACS** in Home Assistant.
2. Click the three dots in the top right, then **Custom repositories**.
3. Paste `https://github.com/barloew/sonos_smart_groups`, choose category
   **Integration**, and click **Add**.
4. Search for **Sonos Smart Groups** and click **Download**.
5. **Restart Home Assistant.**

### Without HACS

Download the latest release, copy the folder
`custom_components/sonos_smart_groups` into your Home Assistant `config` folder
under `custom_components`, and restart Home Assistant.

---

## Setting it up

1. Go to **Settings → Devices & services**.
2. Click **Add integration** and choose **Sonos Smart Groups**.
3. Name the situations that should be able to take over your speakers —
   `Home theater` is a good first one. You get a switch for each. Leave the
   field empty if you do not need precedence yet; you can add them later.

The blueprint installs itself during setup — no reloading needed. Go to
**Settings → Automations & scenes → Blueprints** and **Sonos Smart Group** is
already in the list. Later updates to the integration bring a newer blueprint
with them, unless you have edited yours: then it is left alone and you get a
repair notice instead.

---

## Your first smart group

Picture an open-plan ground floor: kitchen, dining room and living room flowing
into one another, an office off to the side, a gym in the basement. The kitchen
speaker is the one people actually touch.

1. **Settings → Automations & scenes → Create automation → Use blueprint**
2. Pick **Sonos Smart Group**
3. **Leader**: Kitchen
4. **Followers**:

   | Room | Volume factor | Add to group |
   |---|---|---|
   | Dining room | 1.0 | yes |
   | Living room | 1.3 | yes |

5. Save.

That is a complete smart group. Start music in the kitchen and the other two
join, with the living room 30 % louder because it is furthest from the counter.

Sections 3 to 6 of the blueprint stay collapsed on purpose. The defaults are
sensible — leave them until something bothers you.

**To match the sound as well as the volume,** tick *Bass*, *Treble* and
*Loudness* under **Equalizer** in section 2. Controls a speaker does not have
are skipped, so it is safe to tick surround settings for a group that mixes a
soundbar with bookshelf speakers.

---

## Taking precedence

The home theater is a soundbar with a Sub — one Sonos room, in the same open
space as the kitchen and dining room. When a film starts you want the living
room with it and the music group to let go. When the film ends, the music group
should come back exactly as it was.

**The superior smart group** — a second automation from the same blueprint:

| Setting | Value |
|---|---|
| Leader | Home theater |
| Followers | Living room, factor `1.0`, add to group |
| Only for source | `TV` |
| This smart group is | **Superior** |
| Precedence lock | Precedence Home theater |

**The subordinate smart group** — your kitchen group from earlier:

| Setting | Value |
|---|---|
| This smart group is | **Subordinate** |
| Precedence lock | Precedence Home theater |
| When standing down | Join the superior group |
| When precedence is released | Rebuild this smart group |

Start the TV and the home theater takes precedence. Pause the film, wait out the
timeout, and the kitchen group forms itself again.

For a party you would do the reverse: one smart group led by the kitchen with
all six rooms as followers, the gym at `0.7` because it echoes, and the home
theater group simply not involved.

---

## Starting by itself

Section 5 of the blueprint lets a smart group start on its own, on any trigger
you can express.

**Play this** opens the media browser. What you find there is your **Sonos
favourites**, your local **music library**, and **Spotify** or **Plex** if you
use those integrations.

Favourites are the way in to everything else. Apple Music, Tidal, TuneIn, Sonos
Radio, Amazon Music — none of them can be browsed from Home Assistant, but
anything you favourite once in the Sonos app shows up here, sorted into
Playlists, Radio, Albums and the rest. Favourite it once; pick it forever.

**Or switch to this input** covers the physical inputs: `TV` for a soundbar's
own input, `Line-in` for a turntable, plus `AirPlay` and `Spotify Connect`. A
line-in shared from another room appears under that room's name, so a turntable
in the office shows up as `Office` everywhere else.

---

## Using Music Assistant

Music Assistant players work as leaders and followers just like Sonos ones.
Volume factors, mute, transport, grouping, precedence and starting by itself
all behave the same, and both pickers list them alongside your Sonos rooms.

**Grouping stays within one integration.** A smart group can mirror volume and
sound between a Music Assistant player and a Sonos one, but *Add to group* only
works when leader and followers come from the same place. Mixing them produces
a group that is silently incomplete, so that combination is refused and noted
in the log instead. In practice this is rarely a limitation: build the group in
whichever integration you actually control your speakers with.

**The equalizer needs the Sonos integration.** Music Assistant does not offer
bass, treble, surround or night sound as entities for Sonos players — its Sonos
provider covers playback, sources and grouping, and nothing else. Those options
are then skipped rather than broken: everything else in the smart group keeps
working.

If you want both, keep the Sonos integration installed for the equalizer
entities and hide or disable its media players so only the Music Assistant ones
show up. That does mean two controllers talking to the same speakers, which is
worth knowing if your network is at all fragile.

---

## When something does not work

**Followers respond only on the second button press** — the volume tolerance is
too high. Set it to `0.5` in section 6. With a factor of 1.2, one volume step
produces only 1.2 points of difference, and a tolerance of 2 swallows it.

**Nothing happens at all** — open the automation trace. Every condition has a
name, so the trace shows exactly which one stopped the run. Usually it is an
entity under *Only when these are on* being off, or the leader currently being
a follower in a larger group.

**Everything is half a minute late** — that is the Sonos integration, not this
one. Sonos pushes its updates to Home Assistant over TCP port 1400; when those
subscriptions fail, Home Assistant polls every 30 seconds instead. Look for
`Subscription renewal failed` in your log, and check firewalls and VLANs
between your speakers and Home Assistant.

**Groups reassemble by themselves after the TV stops** — Sonos has its own
**TV autoplay** and **Ungroup on autoplay** switches, one pair per room.
Check those before blaming an automation.

**Equalizer settings are not copied** — check that both speakers actually have
the control. A Play:1 has no surround level and no subwoofer gain. Hidden
entities work fine; being hidden is not the problem. Running Music Assistant
without the Sonos integration? Then the controls do not exist at all — see
*Using Music Assistant*.

**Followers get the volume but never join the group** — leader and followers
come from different integrations. The log says so. Build the group within one
of them.

Still stuck? The [advanced guide][advanced] explains the internals and how to
read a trace. Bug reports are welcome in the [issue tracker][issues].

---

## Good to know

- **One direction per automation.** A smart group watches its leader, never its
  followers. Two rooms that should follow each other need two automations
  with reciprocal factors — `1.25` one way, `0.8` the other. That constraint is
  what makes the loop protection reliable.
- **Rebuilding does not use snapshots.** A smart group knows how it should
  look, so it re-applies its own definition. `sonos.snapshot` does not restore
  group topology reliably when the snapshotted speaker was already grouped,
  which is exactly the situation precedence creates.
- **A Sub has no room of its own.** Sonos bonds it to one room, along with the
  surrounds of a home theater set and the halves of a stereo pair, so it never
  appears as something you can pick. It simply plays along with whatever its
  room is doing — hand that room to another group and the Sub goes with it.
  What a smart group *can* copy is the Sub's settings: whether it is on, and
  its gain and crossover.
- **Ad-hoc groups are not preserved.** If you regroup rooms by hand in the
  Sonos app, a smart group rebuilds itself as configured, not as you left it.
- **Equalizer copying works in every language.** Entity IDs are translated;
  the identifiers underneath are not. The [advanced guide][advanced] explains
  how.

---

## Advanced

Architecture, the service API, every configuration option and the reasoning
behind each default: see the [advanced guide][advanced].

The blueprint is a convenience, not a requirement — you can call
`sonos_smart_groups.apply` from your own automations and keep the serialised,
idempotent writes.

## License

Released under the [MIT License](LICENSE). Not affiliated with Sonos, Inc.
"Sonos" is a trademark of its respective owner.

[my-ha-badge]: https://my.home-assistant.io/badges/hacs_repository.svg
[my-ha-url]: https://my.home-assistant.io/redirect/hacs_repository/?owner=barloew&repository=sonos_smart_groups&category=integration
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[hacs-url]: https://github.com/hacs/integration
[validate-badge]: https://github.com/barloew/sonos_smart_groups/actions/workflows/validate.yml/badge.svg
[validate-url]: https://github.com/barloew/sonos_smart_groups/actions/workflows/validate.yml
[release-badge]: https://img.shields.io/github/v/release/barloew/sonos_smart_groups
[release-url]: https://github.com/barloew/sonos_smart_groups/releases
[advanced]: docs/advanced.md
[music-assistant]: https://www.music-assistant.io/
[issues]: https://github.com/barloew/sonos_smart_groups/issues
