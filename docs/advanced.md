# Advanced guide

Everything the [README](../README.md) leaves out: how it works, why it works
that way, and what to reach for when the standard settings are not enough.

---

## Contents

- [Why this is not just an automation](#why-this-is-not-just-an-automation)
- [Architecture](#architecture)
- [Loop protection](#loop-protection)
- [Language independence](#language-independence)
- [Mirrorable properties](#mirrorable-properties)
- [What you can play](#what-you-can-play)
- [Music Assistant](#music-assistant)
- [Precedence internals](#precedence-internals)
- [Service API](#service-api)
- [Calling the services directly](#calling-the-services-directly)
- [Reading a trace](#reading-a-trace)
- [Known limitations](#known-limitations)
- [Translating the blueprint](#translating-the-blueprint)
- [Development](#development)

---

## Why this is not just an automation

Grouping two speakers from an automation is three lines, and for a pair that
should always play together those three lines are the right answer. What
follows is what the remaining evenings go on.

**Followers push back.** Set the kitchen to 30 and the automation sets the bar
to 42. That write lands as a state change, which fires the automation watching
the bar, which writes back to the kitchen. The fix is to compare before
writing — but volumes are floating point, and `0.18 * 100` is
`18.000000000000004`, so "the same" is never exactly the same. You need a
tolerance band, and the band needs choosing with care: too tight and it writes
forever, too loose and a real volume step disappears. With a factor of 1.2, one
press moves the target by 1.2 points, so a tolerance of 2 means nothing happens
until the second press. Hand-written versions usually end up with a delay
bolted on, trading the loop for a system that feels slow.

**Commands collide.** Two groups reacting to the same event interleave their
calls on the Sonos network: a join silently fails, or a speaker stutters.
`mode: queued` serialises one automation with itself, not two automations with
each other, and YAML offers no lock that spans them.

**Dragging a slider is not one event.** It is thirty, and every one is a
trigger.

**The equalizer cannot be done in YAML at all.** Bass lives on
`number.<speaker>_bass` — except the entity ID is generated from the
*translated* name, so a Dutch installation has `..._bas` and a German one
something else again. Matching on properties does not help: bass and treble
share the same range. The untranslated key exists only in the entity's unique
ID, and templates cannot read unique IDs. This is not a matter of writing a
cleverer template; the information is not reachable from one. See
[Language independence](#language-independence).

**Precedence has to carry a name.** An `input_boolean` can say *something has
priority*. It cannot say *attach your speakers to the living room soundbar*,
which is what a group standing down needs to know. See
[Precedence internals](#precedence-internals).

None of this is exotic. It is the ordinary cost of maintaining a relationship
between speakers rather than issuing a one-off command — and it is the reason
this is an integration and not a snippet.

---

## Architecture

Three pieces, each doing what the others cannot.

| Piece | Responsibility |
|---|---|
| **Blueprint** | When something should happen, and to whom. One automation per smart group. |
| **Integration** | How it happens: serialised writes, idempotency, registry lookups. |
| **Precedence locks** | Shared state between smart groups, carrying the principal. |

The split matters. A blueprint alone cannot create helpers, cannot serialise
across automations, and cannot read the entity registry — which is exactly what
equalizer copying needs. An integration alone would mean re-implementing every
trigger and condition Home Assistant already offers. Together, each part does
what it is good at.

### One direction per automation

A smart group is directed: the leader is watched, the followers are not. Two
speakers that should follow each other need two automations with reciprocal
factors, for example `1.25` one way and `0.8` the other.

This is deliberate. A bidirectional relationship in a single automation would
need per-entity origin tracking to suppress echo, and that tracking is exactly
what fails at three in the morning. Two directed automations that each do one
simple thing are easier to reason about and far easier to trace.

---

## Loop protection

Four mechanisms, in the order they take effect.

**1 · Only leaders trigger.** Followers are written to, never watched. A cycle
therefore requires two automations pointing at each other, which only happens
when you deliberately build a mutual pair.

**2 · Idempotency.** The `apply` service compares before it writes. A follower
already at the target volume is left alone, so the echo of a write does not
produce another write and the chain dies on its own. This is the main defence.

**3 · Tolerance.** Floating point makes exact comparison useless: `0.18 * 100`
is `18.000000000000004`. The tolerance is the band within which two values
count as equal.

| Tolerance | Effect |
|---|---|
| `0` | Rounding noise counts as a difference. Writes forever. Never use. |
| `0.5` | Every real volume step (1 point) passes; noise does not. **Recommended.** |
| `2` | With factor 1.2, one step yields 1.2 points of difference — below the threshold. Followers appear to respond only every second press. |

**4 · Settle time.** A `for:` on the volume trigger. Dragging a slider produces
a stream of events; only the final value survives. Set it to `0` if you use
physical remote buttons and want instant response — idempotency still protects
you.

### Serialisation

Every write passes through a single `asyncio.Lock` shared by all smart groups,
so two groups reacting to the same event cannot interleave their commands on
the Sonos network. The command gap adds a pause after each write that actually
happened; skipped writes cost nothing.

---

## Language independence

Entity IDs are generated from translated names, once, when an entity is first
registered — and then frozen. An installation that was Dutch at the time ends
up with `number.sonos_living_room_bas` forever, even after switching Home
Assistant to English.

Matching on entity ID suffixes would therefore only work on English installs.
Matching on properties does not work either: bass and treble share the same
range of −10 to 10, so nothing tells them apart.

The Sonos integration builds unique IDs as `<RINCON-uid>-<key>`, and that key is
never translated:

```
media_player.sonos_living_room        →  RINCON_000E58BE415701400
number.sonos_living_room_bas          →  RINCON_000E58BE415701400-bass
number.sonos_living_room_hoge_tonen   →  RINCON_000E58BE415701400-treble
switch.sonos_living_room_nachtgeluid  →  RINCON_000E58BE415701400-night_mode
```

So the lookup runs through the entity registry:

```python
registry = er.async_get(hass)
entry = registry.async_get(speaker)          # the media_player
uid = entry.unique_id                        # RINCON_…
bass = registry.async_get_entity_id("number", "sonos", f"{uid}-bass")
```

It returns `None` when the speaker has no such control, which is normal and
handled by skipping.

Templates have no access to unique IDs, which is why this could never have been
a blueprint-only feature.

---

## Mirrorable properties

### On the media_player entity

| Key | Notes |
|---|---|
| `volume` | Scaled by the follower's `volume_factor`, clamped to 0–1 |
| `mute` | Copied as-is |
| `source` | Skipped for grouped followers, which follow their coordinator. Only applied when the source appears in the follower's own `source_list` |
| `transport` | Play and pause, only for followers with *Add to group* off |

### Through the entity registry

| Key | Domain | Section | Scalable |
|---|---|---|---|
| `bass` | number | Equalizer | yes, `bass_factor` |
| `treble` | number | Equalizer | yes, `treble_factor` |
| `balance` | number | Equalizer | no — it is a position |
| `loudness` | switch | Equalizer | — |
| `sub_enabled` | switch | Equalizer | — |
| `sub_gain` | number | Equalizer | no |
| `sub_crossover` | number | Equalizer | no |
| `surround_enabled` | switch | Home theater | — |
| `surround_level` | number | Home theater | no |
| `music_surround_level` | number | Home theater | no |
| `surround_mode` | switch | Home theater | full volume for music surround |
| `dialog_level` | switch | Home theater | speech enhancement |
| `night_mode` | switch | Home theater | night sound |
| `audio_delay` | number | Home theater | no — a lip-sync correction |
| `cross_fade` | switch | Playback | — |

Numeric values are clamped to the target's own `min` and `max` and rounded to
its `step` before writing, so speakers with different ranges do not fight.

Not every speaker has every control — subwoofer gain and crossover in
particular only appear on some models. Missing controls are skipped without
complaint.

---

## What you can play

`root_payload()` in the Sonos integration's media browser offers exactly five
entries, and only when they apply:

| Entry | Condition |
|---|---|
| **Favorites** | the speaker has Sonos favourites |
| **Music Library** | a local music share is configured |
| **Plex** | the Plex integration is set up |
| **Spotify** | the Spotify integration is set up |
| **Media source** | always — TTS and `/config/media` |

There is no catalogue browsing for Apple Music, Tidal, TuneIn, Sonos Radio,
Amazon Music or Deezer. The integration never sees those services; it sees what
the speaker reports.

**Favourites are the bridge.** Whatever you favourite in the Sonos app, from
any service, appears under Favorites. `favorites_payload()` groups them by
`item_class` through `SONOS_TYPES_MAPPING`, which is why a TuneIn station lands
under Radio and a Tidal playlist under Playlists.

**Favourites are referenced, not named.** The blueprint stores the
`media_content_id` the browser returned. Rename or delete the favourite in the
Sonos app and that reference breaks — the automation will fail rather than play
something else, but it will fail silently until you look at the trace.

For real browsing of streaming services, [Music Assistant][ma] is the usual
answer; it runs alongside the Sonos integration and provides its own players.

[ma]: https://www.music-assistant.io/

---

## Music Assistant

Music Assistant's Sonos provider speaks the S2 websocket API through
`aiosonos`, while the Home Assistant Sonos integration uses SoCo over UPnP.
Two protocol stacks, one set of speakers — but they are not separate worlds:
MA's `modify_group_members()` and `leave_group()` manipulate the **native**
Sonos group, so a group formed on one side shows up in the other's
`group_members`. It also means both can write, so let one of them own the
grouping.

### Why the registry lookup works unchanged

The Music Assistant entity's `unique_id` is its MA `player_id`:

```python
# music_assistant/entity.py
_base = self.player_id
```

and the Sonos provider sets that player_id to the speaker's UUID:

```python
# music_assistant/providers/sonos/player.py
# The player_id is the Sonos UUID (e.g., RINCON_xxxxxxxxxxxx)
```

That is the same string the Sonos integration uses for its `media_player`, so
`_related_entity()` resolves `<uid>-bass` from a Music Assistant entity without
a special case. Players from other providers yield no match and are skipped.

### What Music Assistant does not provide

The MA Home Assistant integration *does* create number, select and switch
entities from player options, with the right translation keys —
`bass`, `treble`, `subwoofer_volume`, `dialogue_level` and the equalizer bands.
They are filled from `player.options`, and the Sonos provider declares none.
Its feature set is:

```
PLAY_MEDIA · PAUSE · SEEK · SELECT_SOURCE · SET_MEMBERS · GAPLESS_PLAYBACK
```

So equalizer and home theater mirroring depend entirely on the Sonos
integration being installed; it is that integration which creates the number
and switch entities. Without it those keys resolve to `None` and are skipped.

### Grouping across integrations

`async_join_players()` resolves the entity IDs you pass it back to MA
player_ids through the entity registry, and the Sonos integration expects its
own entities. A join that mixes the two produces a group that is silently
incomplete, so `apply` compares the platforms of leader and follower first and
refuses the join with a warning in the log. Volume, mute and the registry-based
settings are still applied — only the grouping is skipped.

### Announcements

MA supports `announce: true` on `play_media`, but reads its volume from
`extra.announce_volume` rather than the Sonos integration's `extra.volume`.
Sending both is harmless: each side ignores the key it does not know.

---

## Precedence internals

A precedence lock is a `SwitchEntity` with three extra attributes:

| Attribute | Meaning |
|---|---|
| `principal` | The leader of the smart group currently holding the lock |
| `previous_principal` | Who held it before, for diagnostics |
| `taken_at` | UTC timestamp of the last take |

`principal` is why this is an entity rather than an `input_boolean`. A plain
flag can say *someone has priority*; it cannot say *attach yourself to the
living room soundbar*. Subordinate groups read the attribute to know where to
send their speakers. The lock is a `RestoreEntity`, so it survives a restart.

### Flow

```
Superior leader starts playing
  → take_precedence(lock, principal=leader)
  → lock turns on, principal recorded
      → each subordinate group sees the state change
      → unjoins its own speakers, joins the principal

Superior leader stops
  → wait out the timeout
  → still stopped, and hold switch not on?
  → release_precedence(lock)
      → each subordinate group unjoins
      → re-applies its own definition
```

### Why rebuilding beats snapshots

A smart group knows how it should look — that is its whole definition.
Restoring means re-running `apply`, not replaying stored state.

`sonos.snapshot` with `with_group: true` is the obvious alternative and it is
unreliable: group topology is not restored correctly when the snapshotted
speaker was itself already grouped, which is precisely the situation precedence
creates.

The cost is that ad-hoc groups made by hand in the Sonos app are not restored.
Choose **Leave everything as it is** if you would rather sort that out yourself.

### Chains and multiple locks

Nothing stops a smart group being superior on one lock and subordinate on
another, but one automation takes one lock. For a chain — doorbell outranks
home theater outranks music — create separate automations per role and let them
stack.

Careful with cycles: if A stands down for B while B stands down for A, the
two will hand speakers back and forth. Precedence is not cycle-checked.

---

## Service API

### `sonos_smart_groups.apply`

Mirrors a leader onto its followers. Serialised and idempotent.

| Field | Type | Default | Notes |
|---|---|---|---|
| `leader` | entity_id | — | required |
| `followers` | list of dicts | — | required, see below |
| `mirror` | list of keys | `[volume, mute]` | any key from the tables above |
| `tolerance` | float | `0.5` | volume points |
| `gap_ms` | int | `120` | pause after each write |

Follower dict:

| Key | Default | Notes |
|---|---|---|
| `speaker` | — | required |
| `volume_factor` | `1.0` | |
| `bass_factor` | `1.0` | only used when `bass` is mirrored |
| `treble_factor` | `1.0` | only used when `treble` is mirrored |
| `join` | `false` | add to the leader's group |

### `sonos_smart_groups.take_precedence`

| Field | Notes |
|---|---|
| `lock` | a precedence lock switch |
| `principal` | the leader other groups should attach to |

### `sonos_smart_groups.release_precedence`

| Field | Notes |
|---|---|
| `lock` | a precedence lock switch |

---

## Calling the services directly

The blueprint is a convenience, not a requirement. For a layout the blueprint
does not express, call the service from your own automation:

```yaml
- action: sonos_smart_groups.apply
  data:
    leader: media_player.kitchen
    followers:
      - speaker: media_player.dining_room
        volume_factor: 1.0
        join: true
      - speaker: media_player.living_room
        volume_factor: 1.3
        bass_factor: 0.8
        join: true
      - speaker: media_player.gym
        volume_factor: 0.7
        join: true
    mirror: [volume, mute, bass, treble, loudness]
    tolerance: 0.5
```

You still get serialisation, idempotency and registry lookups; you supply your
own triggers and conditions.

---

## Reading a trace

Every condition in the blueprint has an `alias`, so a trace names the step that
stopped a run rather than showing an anonymous index.

**Settings → Automations & scenes**, open the automation, then the three dots →
**Traces**. The *Step Details* pane shows each condition with its result. The
ones worth recognising:

| Alias | Means |
|---|---|
| *Required switches are on* | Something under *Only when these are on* is off |
| *The leader is in charge of its own group* | The leader is currently a follower elsewhere |
| *Not currently standing down for a superior group* | A precedence lock is held by someone else |
| *Source matches* | The leader is on a different input than configured |
| *Cooldown has passed* | The automation ran too recently |

For the writes themselves, turn on debug logging:

```yaml
logger:
  logs:
    custom_components.sonos_smart_groups: debug
```

Skipped speakers are logged with the reason; skipped writes are silent by
design, since that is the normal case.

---

## Known limitations

**Timers do not survive a reload.** A `for:` in the middle of its window, or a
precedence timeout counting down, is lost when automations are reloaded or Home
Assistant restarts. The next event recovers the situation.

**Precedence has no cycle detection.** Two groups yielding to each other's
locks will pass speakers back and forth.

**Source mirroring is best-effort.** A source is only selected when it appears
in the follower's own `source_list`. `TV` exists only on soundbars, `Line-in`
only on a Connect, Port, Amp or Play:5.

**Ad-hoc groups are not preserved.** See *Why rebuilding beats snapshots*.

**Sonos has its own opinions.** The per-speaker **TV autoplay** and **Ungroup
on autoplay** switches act independently of anything here. If groups reassemble
without an automation running, look there first.

---

## Translating the blueprint

Home Assistant has no translation mechanism for blueprint labels and
descriptions — selector labels are literal strings. A translated blueprint is
therefore a separate file.

1. Copy `sonos_smart_group.yaml` to `sonos_smart_group.<language>.yaml`
2. Translate `blueprint.name`, `blueprint.description`, and every `name` and
   `description` under `input`
3. **Leave everything else untouched** — input keys, `!input` references,
   trigger IDs and the `value` fields of select options are structural

Drop the file in `custom_components/sonos_smart_groups/blueprints/` and it is
installed alongside the English one, so users pick their language from the
blueprint list.

Integration text is ordinary Home Assistant translation:
`translations/<language>.json`, mirroring the structure of `strings.json`.
Pull requests welcome.

---

## Development

### Layout

```
custom_components/sonos_smart_groups/
├── __init__.py        services, blueprint installation, the apply logic
├── config_flow.py     setup and options
├── const.py           the Sonos property keys
├── switch.py          precedence locks
├── manifest.json
├── services.yaml
├── strings.json
├── brand/             icon.png and logo.png
├── blueprints/        installed into the user's config on setup
└── translations/
```

### Blueprint installation

On `async_setup_entry`, every `*.yaml` in `blueprints/` is copied to
`blueprints/automation/sonos_smart_groups/` in the user's config directory.
**Existing files are never overwritten**, so an edited blueprint survives an
upgrade. Delete the file and reload the integration to get the bundled version
back.

Afterwards the automation blueprint cache is dropped, so the blueprint is
usable straight away without the *Reload blueprints* menu item:

```python
domain_blueprints = hass.data["blueprint"]["automation"]
await domain_blueprints.async_reset_cache()
```

This is precisely what that menu item does. The object lives in another
integration's `hass.data`, so it is reached by name rather than by import —
that keeps it out of the manifest — and every step is optional: it is created
lazily, and on a first install it may not exist yet. That is harmless, because
`_load_blueprints()` rescans the folder on each call and picks up files it has
never seen. The cache reset matters for files that *changed*, which is why it
runs even when nothing was copied.

### Adding a mirrorable property

1. Add the Sonos key to the right list in `const.py`
2. Add it to the matching selector in section 2 of the blueprint
3. If it should be scalable, add it to `FACTORED_KEYS` with a follower key, and
   add that key to the follower object selector

Nothing else changes: `apply` derives its behaviour from those lists.

### Validation

`.github/workflows/validate.yml` runs `hassfest` and the HACS action on every
push, pull request and weekly.
