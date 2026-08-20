"""Sonos Smart Groups.

Adds the plumbing a blueprint cannot provide on its own:

* Precedence locks as real switch entities that remember which speaker is the
  principal, so a subordinate group knows where to attach itself.
* One serialised write path, so several smart groups never issue overlapping
  commands to the Sonos network.
* Idempotent writes: nothing is sent when a speaker already holds the target
  value. This is what stops feedback loops before they can start.
* Language-independent lookup of equalizer and home theater entities through
  the entity registry.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .const import (
    AUTOMATION_COMPONENT,
    ATTR_FOLLOWERS,
    ATTR_GAP_MS,
    ATTR_LEADER,
    ATTR_LOCK,
    ATTR_MIRROR,
    ATTR_PRINCIPAL,
    ATTR_TOLERANCE,
    BLUEPRINT_COMPONENT,
    BLUEPRINT_FILENAME,
    BLUEPRINT_LANGUAGES,
    BLUEPRINT_TARGET,
    CONF_FLAVOUR,
    DEFAULT_FLAVOUR,
    DEFAULT_LANGUAGE,
    FLAVOURS,
    ISSUE_BLUEPRINT_MODIFIED,
    DEFAULT_FACTOR,
    DEFAULT_GAP_MS,
    DEFAULT_TOLERANCE,
    DOMAIN,
    FACTORED_KEYS,
    KEY_JOIN,
    KEY_SPEAKER,
    KEY_VOLUME_FACTOR,
    MIRROR_MUTE,
    MIRROR_OPTIONS,
    MIRROR_SOURCE,
    MIRROR_TRANSPORT,
    MIRROR_VOLUME,
    NUMBER_KEYS,
    REGISTRY_KEYS,
    SERVICE_APPLY,
    SERVICE_RELEASE,
    SERVICE_TAKE,
    SONOS_DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
    SWITCH_KEYS,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS: list[Platform] = [Platform.SWITCH]

FOLLOWER_SCHEMA = vol.Schema(
    {
        vol.Required(KEY_SPEAKER): cv.entity_id,
        vol.Optional(KEY_VOLUME_FACTOR, default=DEFAULT_FACTOR): vol.Coerce(float),
        vol.Optional(KEY_JOIN, default=False): cv.boolean,
    },
    extra=vol.ALLOW_EXTRA,
)

APPLY_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_LEADER): cv.entity_id,
        vol.Required(ATTR_FOLLOWERS): vol.All(cv.ensure_list, [FOLLOWER_SCHEMA]),
        vol.Optional(ATTR_MIRROR, default=[MIRROR_VOLUME, MIRROR_MUTE]): vol.All(
            cv.ensure_list, [vol.In(MIRROR_OPTIONS)]
        ),
        vol.Optional(ATTR_TOLERANCE, default=DEFAULT_TOLERANCE): vol.Coerce(float),
        vol.Optional(ATTR_GAP_MS, default=DEFAULT_GAP_MS): vol.Coerce(int),
    }
)

TAKE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_LOCK): cv.entity_id,
        vol.Required(ATTR_PRINCIPAL): cv.entity_id,
    }
)

RELEASE_SCHEMA = vol.Schema({vol.Required(ATTR_LOCK): cv.entity_id})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up shared state."""
    hass.data.setdefault(DOMAIN, {}).setdefault("lock", asyncio.Lock())
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Sonos Smart Groups entry."""
    hass.data.setdefault(DOMAIN, {}).setdefault("lock", asyncio.Lock())

    await _async_install_blueprints(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _register_services(hass)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when the precedence locks change."""
    await hass.config_entries.async_reload(entry.entry_id)


# ---------------------------------------------------------------------------
# Blueprint installation
# ---------------------------------------------------------------------------


def _pick_variant(hass: HomeAssistant, entry: ConfigEntry) -> tuple[str, str]:
    """Which flavour and language of the blueprint this system should get."""
    flavour = entry.options.get(
        CONF_FLAVOUR, entry.data.get(CONF_FLAVOUR, DEFAULT_FLAVOUR)
    )
    if flavour not in FLAVOURS:
        flavour = DEFAULT_FLAVOUR

    language = (hass.config.language or DEFAULT_LANGUAGE).split("-")[0].lower()
    if language not in BLUEPRINT_LANGUAGES:
        language = DEFAULT_LANGUAGE

    return flavour, language


async def _async_install_blueprints(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Install the blueprint that matches this system, and drop the others.

    We ship one file per flavour and language. Only the matching one is
    installed, always under the same name, so switching language or flavour
    replaces it rather than leaving a second copy in the list.

    Telling an untouched file from an edited one is the delicate part.
    Overwriting blindly destroys the user's work; never overwriting means a fix
    can only reach them by hand. So the SHA-256 of every file we write is kept
    in a `Store` under `.storage`:

        file missing               -> install it
        hash matches the bundled   -> already current
        hash matches what we wrote -> untouched, replace it
        hash matches neither       -> edited, leave alone and raise an issue
    """
    flavour, language = _pick_variant(hass, entry)
    source = Path(__file__).parent / "blueprints" / flavour / f"{language}.yaml"
    if not source.is_file():
        source = Path(__file__).parent / "blueprints" / flavour / f"{DEFAULT_LANGUAGE}.yaml"
    if not source.is_file():
        _LOGGER.warning("No bundled blueprint found for %s/%s", flavour, language)
        return

    target_dir = Path(hass.config.path(BLUEPRINT_TARGET))
    destination = target_dir / BLUEPRINT_FILENAME

    store: Store[dict[str, str]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    known: dict[str, str] = await store.async_load() or {}

    def _sync() -> tuple[str | None, bool, bool]:
        """Returns (new hash, did we write, should we report it as edited)."""
        target_dir.mkdir(parents=True, exist_ok=True)
        bundled = source.read_bytes()
        bundled_hash = hashlib.sha256(bundled).hexdigest()

        if not destination.exists():
            destination.write_bytes(bundled)
            return bundled_hash, True, False

        current_hash = hashlib.sha256(destination.read_bytes()).hexdigest()
        if current_hash == bundled_hash:
            return bundled_hash, False, False

        if known.get(BLUEPRINT_FILENAME) == current_hash:
            destination.write_bytes(bundled)
            return bundled_hash, True, False

        return None, False, True

    try:
        new_hash, wrote, edited = await hass.async_add_executor_job(_sync)
    except OSError as err:  # pragma: no cover - filesystem dependent
        _LOGGER.warning("Could not install the blueprint: %s", err)
        return

    if new_hash and known.get(BLUEPRINT_FILENAME) != new_hash:
        await store.async_save({**known, BLUEPRINT_FILENAME: new_hash})

    if wrote:
        await _async_reset_blueprint_cache(hass)
        _LOGGER.info(
            "Installed the %s blueprint in %s", flavour.replace("_", " "), language
        )

    ir.async_delete_issue(hass, DOMAIN, ISSUE_BLUEPRINT_MODIFIED)
    if edited:
        _async_report_skipped(hass)

    await _async_remove_stale_blueprints(hass)


async def _async_remove_stale_blueprints(hass: HomeAssistant) -> None:
    """Remove blueprints from earlier versions that shipped one file per name.

    Home Assistant refuses to delete a blueprint an automation still uses, so
    anything still in service simply stays put.
    """
    domain_blueprints = (hass.data.get(BLUEPRINT_COMPONENT) or {}).get(
        AUTOMATION_COMPONENT
    )
    if domain_blueprints is None:
        return

    folder = Path(hass.config.path(BLUEPRINT_TARGET))

    def _stale() -> list[str]:
        if not folder.is_dir():
            return []
        return [
            item.name
            for item in sorted(folder.glob("*.yaml"))
            if item.name != BLUEPRINT_FILENAME
        ]

    try:
        stale = await hass.async_add_executor_job(_stale)
    except OSError:  # pragma: no cover - filesystem dependent
        return

    for name in stale:
        relative = f"{Path(BLUEPRINT_TARGET).name}/{name}"
        try:
            await domain_blueprints.async_remove_blueprint(relative)
        except Exception:  # noqa: BLE001 - in use, missing, or not ours
            _LOGGER.debug("Left %s in place", name, exc_info=True)
        else:
            _LOGGER.info("Removed the now-unused blueprint %s", name)


@callback
def _async_report_skipped(hass: HomeAssistant) -> None:
    """Tell the user we did not dare to overwrite their edited blueprint."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_BLUEPRINT_MODIFIED,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_BLUEPRINT_MODIFIED,
        translation_placeholders={
            "name": BLUEPRINT_FILENAME,
            "path": f"{BLUEPRINT_TARGET}/{BLUEPRINT_FILENAME}",
        },
    )
    _LOGGER.info(
        "Left %s alone: it differs from the version shipped with this "
        "integration, so it looks edited. Delete it and reload the integration "
        "to get the bundled version",
        BLUEPRINT_FILENAME,
    )


async def _async_reset_blueprint_cache(hass: HomeAssistant) -> None:
    """Drop the automation blueprint cache so new files appear immediately.

    The blueprint component keeps a DomainBlueprints object per domain in
    `hass.data["blueprint"]["automation"]`, and resetting its cache is exactly
    what the "Reload blueprints" menu item does. Doing it here saves the user
    a step after installation, and matters after an update, when the path was
    already cached with the old contents.

    Deliberately defensive: this reaches into another integration's data, so
    every failure is non-fatal. The worst case is the old behaviour, where the
    user reloads blueprints by hand.
    """
    domain_blueprints = (hass.data.get(BLUEPRINT_COMPONENT) or {}).get(
        AUTOMATION_COMPONENT
    )
    reset = getattr(domain_blueprints, "async_reset_cache", None)
    if reset is None:
        _LOGGER.debug("No automation blueprint cache to reset yet")
        return

    try:
        await reset()
    except Exception:  # noqa: BLE001 - never let this break setup
        _LOGGER.debug("Could not reset the blueprint cache", exc_info=True)


# ---------------------------------------------------------------------------
# Registry lookup
# ---------------------------------------------------------------------------


def _related_entity(hass: HomeAssistant, speaker: str, key: str) -> str | None:
    """Find the entity that carries `key` for the given Sonos speaker.

    The Sonos integration builds unique_ids as `<RINCON-uid>-<key>`, where the
    key is never translated. Entity_ids are, so this is the only reliable way
    to find the bass control on a non-English installation.

    This also works for Music Assistant players, without a special case: the
    Music Assistant entity's unique_id is its MA player_id, and for the Sonos
    provider that player_id *is* the RINCON uid. A player from any other
    provider simply yields no match.

    Returns None when the speaker does not have that control at all, which is
    normal: a bookshelf speaker has no surround level, and a Music Assistant
    player has none of them unless the Sonos integration is also installed —
    it is that integration which creates the number and switch entities.
    """
    registry = er.async_get(hass)
    if (entry := registry.async_get(speaker)) is None:
        return None

    domain = "number" if key in NUMBER_KEYS else "switch"
    return registry.async_get_entity_id(domain, SONOS_DOMAIN, f"{entry.unique_id}-{key}")


@callback
def _same_platform(hass: HomeAssistant, first: str, second: str) -> bool:
    """Whether two media players are provided by the same integration.

    Grouping only works within one integration: Music Assistant resolves the
    entities you hand it back to its own player_ids, and the Sonos integration
    expects its own. Mixing the two in a single join produces a group that is
    silently incomplete.
    """
    registry = er.async_get(hass)
    first_entry = registry.async_get(first)
    second_entry = registry.async_get(second)
    if first_entry is None or second_entry is None:
        return True  # unknown; let the call through rather than guess
    return first_entry.platform == second_entry.platform


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------


def _register_services(hass: HomeAssistant) -> None:
    """Register services once."""
    if hass.services.has_service(DOMAIN, SERVICE_APPLY):
        return

    async def _async_apply(call: ServiceCall) -> None:
        await _async_handle_apply(hass, call)

    async def _async_take(call: ServiceCall) -> None:
        await hass.services.async_call(
            "switch", "turn_on", {ATTR_ENTITY_ID: call.data[ATTR_LOCK]}, blocking=True
        )
        entity = hass.data.get(DOMAIN, {}).get("locks", {}).get(call.data[ATTR_LOCK])
        if entity is None:
            _LOGGER.warning(
                "%s is not a Sonos Smart Groups precedence lock; principal not stored",
                call.data[ATTR_LOCK],
            )
            return
        entity.set_principal(call.data[ATTR_PRINCIPAL])

    async def _async_release(call: ServiceCall) -> None:
        await hass.services.async_call(
            "switch", "turn_off", {ATTR_ENTITY_ID: call.data[ATTR_LOCK]}, blocking=True
        )

    hass.services.async_register(DOMAIN, SERVICE_APPLY, _async_apply, schema=APPLY_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_TAKE, _async_take, schema=TAKE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_RELEASE, _async_release, schema=RELEASE_SCHEMA
    )


async def _async_handle_apply(hass: HomeAssistant, call: ServiceCall) -> None:
    """Mirror the leader onto its followers."""
    leader: str = call.data[ATTR_LEADER]
    followers: list[dict] = call.data[ATTR_FOLLOWERS]
    mirror = set(call.data[ATTR_MIRROR])
    tolerance: float = call.data[ATTR_TOLERANCE]
    gap = max(0, call.data[ATTR_GAP_MS]) / 1000

    lock: asyncio.Lock = hass.data[DOMAIN]["lock"]

    async with lock:
        leader_state = hass.states.get(leader)
        if leader_state is None or leader_state.state in ("unavailable", "unknown"):
            _LOGGER.debug("Leader %s unavailable; nothing applied", leader)
            return

        members = leader_state.attributes.get("group_members") or []
        registry_wanted = [key for key in REGISTRY_KEYS if key in mirror]

        for follower in followers:
            speaker: str = follower[KEY_SPEAKER]
            state = hass.states.get(speaker)
            if state is None or state.state in ("unavailable", "unknown"):
                _LOGGER.debug("Follower %s unavailable; skipped", speaker)
                continue

            wrote = False
            wrote |= await _async_apply_media_player(
                hass, leader, leader_state, speaker, state, follower, mirror,
                members, tolerance,
            )
            wrote |= await _async_apply_registry_keys(
                hass, leader, speaker, follower, registry_wanted, tolerance
            )

            if wrote and gap:
                await asyncio.sleep(gap)


async def _async_apply_media_player(
    hass, leader, leader_state, speaker, state, follower, mirror, members, tolerance
) -> bool:
    """Mirror the properties that live on the media_player entity itself."""
    wrote = False
    factor = float(follower.get(KEY_VOLUME_FACTOR, DEFAULT_FACTOR))
    join = bool(follower.get(KEY_JOIN, False))

    if MIRROR_VOLUME in mirror:
        leader_volume = leader_state.attributes.get("volume_level")
        if leader_volume is not None:
            target = min(1.0, max(0.0, leader_volume * factor))
            current = state.attributes.get("volume_level")
            if current is None or abs(current * 100 - target * 100) >= tolerance:
                await hass.services.async_call(
                    "media_player",
                    "volume_set",
                    {ATTR_ENTITY_ID: speaker, "volume_level": round(target, 3)},
                    blocking=True,
                )
                wrote = True

    if MIRROR_MUTE in mirror:
        muted = leader_state.attributes.get("is_volume_muted")
        if muted is not None and state.attributes.get("is_volume_muted") != muted:
            await hass.services.async_call(
                "media_player",
                "volume_mute",
                {ATTR_ENTITY_ID: speaker, "is_volume_muted": muted},
                blocking=True,
            )
            wrote = True

    # Source and transport only make sense for followers that stay out of the
    # group; a grouped speaker already follows its coordinator.
    if MIRROR_SOURCE in mirror and speaker not in members:
        source = leader_state.attributes.get("source")
        available = state.attributes.get("source_list") or []
        if source and source in available and state.attributes.get("source") != source:
            await hass.services.async_call(
                "media_player",
                "select_source",
                {ATTR_ENTITY_ID: speaker, "source": source},
                blocking=True,
            )
            wrote = True

    if join and speaker not in members:
        if not _same_platform(hass, leader, speaker):
            _LOGGER.warning(
                "Not grouping %s with %s: they come from different integrations. "
                "Grouping only works within one integration; mirror volume and "
                "EQ across them instead, and leave 'Add to group' off",
                speaker,
                leader,
            )
        else:
            await hass.services.async_call(
                "media_player",
                "join",
                {ATTR_ENTITY_ID: leader, "group_members": [speaker]},
                blocking=True,
            )
            wrote = True

    if MIRROR_TRANSPORT in mirror and not join:
        if leader_state.state == "playing" and state.state != "playing":
            await hass.services.async_call(
                "media_player", "media_play", {ATTR_ENTITY_ID: speaker}, blocking=True
            )
            wrote = True
        elif leader_state.state == "paused" and state.state == "playing":
            await hass.services.async_call(
                "media_player", "media_pause", {ATTR_ENTITY_ID: speaker}, blocking=True
            )
            wrote = True

    return wrote


async def _async_apply_registry_keys(
    hass, leader, speaker, follower, keys, tolerance
) -> bool:
    """Mirror equalizer and home theater settings.

    Both sides are looked up through the entity registry, so a control that
    only one of the two speakers has is skipped silently.
    """
    wrote = False

    for key in keys:
        source_entity = _related_entity(hass, leader, key)
        target_entity = _related_entity(hass, speaker, key)
        if not source_entity or not target_entity:
            continue

        source_state = hass.states.get(source_entity)
        target_state = hass.states.get(target_entity)
        if source_state is None or target_state is None:
            continue
        if source_state.state in ("unknown", "unavailable"):
            continue

        if key in SWITCH_KEYS:
            desired = source_state.state
            if desired not in ("on", "off") or target_state.state == desired:
                continue
            await hass.services.async_call(
                "switch",
                "turn_on" if desired == "on" else "turn_off",
                {ATTR_ENTITY_ID: target_entity},
                blocking=True,
            )
            wrote = True
            continue

        # Numeric control.
        try:
            value = float(source_state.state)
        except (TypeError, ValueError):
            continue

        if (factor_key := FACTORED_KEYS.get(key)) is not None:
            value *= float(follower.get(factor_key, DEFAULT_FACTOR))

        low = target_state.attributes.get("min")
        high = target_state.attributes.get("max")
        if low is not None:
            value = max(float(low), value)
        if high is not None:
            value = min(float(high), value)

        step = target_state.attributes.get("step") or 1
        value = round(value / float(step)) * float(step)

        try:
            current = float(target_state.state)
        except (TypeError, ValueError):
            current = None

        if current is not None and abs(current - value) < max(tolerance, float(step)) / 2:
            continue

        await hass.services.async_call(
            "number",
            "set_value",
            {ATTR_ENTITY_ID: target_entity, "value": value},
            blocking=True,
        )
        wrote = True

    return wrote
