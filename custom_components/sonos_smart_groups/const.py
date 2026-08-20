"""Constants for Sonos Smart Groups.

The mirrored property keys below are the ones the Sonos integration itself
uses in its unique_ids (`<RINCON-uid>-<key>`). Matching on those rather than
on entity_ids is what makes this work in every language: a Dutch install names
the entity `number.sonos_living_room_bas`, a German one something else again,
but both carry the unique_id suffix `-bass`.
"""

DOMAIN = "sonos_smart_groups"
SONOS_DOMAIN = "sonos"

# Config / options keys
CONF_LOCKS = "precedence_locks"

# Services
SERVICE_APPLY = "apply"
SERVICE_TAKE = "take_precedence"
SERVICE_RELEASE = "release_precedence"

# Service fields
ATTR_LEADER = "leader"
ATTR_FOLLOWERS = "followers"
ATTR_MIRROR = "mirror"
ATTR_TOLERANCE = "tolerance"
ATTR_GAP_MS = "gap_ms"
ATTR_LOCK = "lock"
ATTR_PRINCIPAL = "principal"

# Follower keys
KEY_SPEAKER = "speaker"
KEY_VOLUME_FACTOR = "volume_factor"
KEY_BASS_FACTOR = "bass_factor"
KEY_TREBLE_FACTOR = "treble_factor"
KEY_JOIN = "join"

# --- Mirrorable properties --------------------------------------------------
# Handled directly on the media_player entity.
MIRROR_VOLUME = "volume"
MIRROR_MUTE = "mute"
MIRROR_SOURCE = "source"
MIRROR_TRANSPORT = "transport"

MEDIA_PLAYER_KEYS = [MIRROR_VOLUME, MIRROR_MUTE, MIRROR_SOURCE, MIRROR_TRANSPORT]

# Equalizer — resolved through the entity registry.
EQ_NUMBER_KEYS = ["bass", "treble", "balance", "sub_gain", "sub_crossover"]
EQ_SWITCH_KEYS = ["loudness", "sub_enabled"]

# Home theater — only present on soundbars and amps.
HT_NUMBER_KEYS = ["surround_level", "music_surround_level", "audio_delay"]
HT_SWITCH_KEYS = [
    "surround_enabled",
    "surround_mode",
    "night_mode",
    "dialog_level",
]

# Playback behaviour.
PLAYBACK_SWITCH_KEYS = ["cross_fade"]

NUMBER_KEYS = EQ_NUMBER_KEYS + HT_NUMBER_KEYS
SWITCH_KEYS = EQ_SWITCH_KEYS + HT_SWITCH_KEYS + PLAYBACK_SWITCH_KEYS
REGISTRY_KEYS = NUMBER_KEYS + SWITCH_KEYS

MIRROR_OPTIONS = MEDIA_PLAYER_KEYS + REGISTRY_KEYS

# Which numeric properties may be scaled per follower, and the follower key
# that carries the factor. Balance is a position and audio delay is a timing
# correction, so neither is scaled.
FACTORED_KEYS = {
    "bass": KEY_BASS_FACTOR,
    "treble": KEY_TREBLE_FACTOR,
}

DEFAULT_TOLERANCE = 0.5
DEFAULT_GAP_MS = 120
DEFAULT_FACTOR = 1.0

# Precedence lock attributes.
ATTR_TAKEN_AT = "taken_at"
ATTR_PREVIOUS_PRINCIPAL = "previous_principal"

BLUEPRINT_TARGET = "blueprints/automation/sonos_smart_groups"

# Where the hashes of the blueprints we installed are remembered, so an update
# can tell an untouched file from one the user edited.
STORAGE_KEY = f"{DOMAIN}.blueprints"
STORAGE_VERSION = 1

# Repair issue raised when a bundled blueprint has moved on but the local copy
# was edited, so we leave it alone.
ISSUE_BLUEPRINT_MODIFIED = "blueprint_modified"

# Reached by name rather than import, so no manifest dependency is needed just
# to drop the blueprint cache after installing our own blueprints.
BLUEPRINT_COMPONENT = "blueprint"
AUTOMATION_COMPONENT = "automation"
