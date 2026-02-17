import re

from loguru import logger
from rich.progress import Progress
from pyarr import SonarrAPI

import tagarr.modules.pytmdb as pytmdb
import tagarr.utils.filters as filters

from tagarr.modules.justwatch import JustWatch
from tagarr.modules.justwatch.exceptions import JustWatchNotFound, JustWatchTooManyRequests


class SonarrActions:
    def __init__(self, url, api_key, locale):
        logger.debug(f"Initializing PySonarr")
        self.sonarr_client = SonarrAPI(url, api_key, ver_uri="/v3")

        logger.debug(f"Initializing JustWatch API with locale: {locale}")
        self.justwatch_client = JustWatch(locale)

        # Cache for tags: label -> tag_id
        self._tag_cache = {}

    def _load_tags(self):
        """Load all existing tags from Sonarr into the cache."""
        logger.debug("Loading existing tags from Sonarr")
        tags = self.sonarr_client.get_tag()
        self._tag_cache = {tag["label"].lower(): tag["id"] for tag in tags}

    @staticmethod
    def _sanitize_tag(label):
        """Sanitize a label for use as a Sonarr tag (only a-z, 0-9, -)."""
        label = label.lower().replace(" ", "-")
        label = re.sub(r"[^a-z0-9-]", "", label)
        return label.strip("-")

    def _get_or_create_tag(self, label):
        """Get a tag ID by label, creating it if it doesn't exist."""
        label = self._sanitize_tag(label)

        if label in self._tag_cache:
            return self._tag_cache[label]

        logger.debug(f"Creating new tag: {label}")
        result = self.sonarr_client.create_tag(label)
        self._tag_cache[label] = result["id"]
        return result["id"]

    def _get_jw_serie_data(self, title, jw_entry):
        jw_id = jw_entry["id"]
        jw_serie_data = {}
        jw_imdb_ids = []
        jw_tmdb_ids = []

        try:
            logger.debug(f"Querying JustWatch API with ID: {jw_id} for title: {title}")
            jw_serie_data = self.justwatch_client.get_show(jw_id)

            jw_imdb_ids = filters.get_imdb_ids(jw_serie_data.get("external_ids", []))
            logger.debug(f"Got IMDB ID's: {jw_imdb_ids} from JustWatch API")

            jw_tmdb_ids = filters.get_tmdb_ids(jw_serie_data.get("external_ids", []))
            logger.debug(f"Got TMDB ID's: {jw_tmdb_ids} from JustWatch API")
        except JustWatchNotFound:
            logger.warning(f"Could not find title: {title} with JustWatch ID: {jw_id}")
        except JustWatchTooManyRequests:
            logger.error(f"JustWatch API returned 'Too Many Requests'")

        return jw_serie_data, jw_imdb_ids, jw_tmdb_ids

    def _find_using_imdb_id(self, title, sonarr_id, imdb_id, fast, jw_query_payload={}):
        logger.debug(
            f"Processing title: {title} with Sonarr ID: {sonarr_id} and IMDB ID: {imdb_id}"
        )

        logger.debug(f"Query JustWatch API with title: {title}")
        jw_query_data = self.justwatch_client.query_title(title, "show", fast, **jw_query_payload)

        for entry in jw_query_data["items"]:
            jw_id = entry["id"]
            jw_serie_data, jw_imdb_ids, _ = self._get_jw_serie_data(title, entry)

            if imdb_id in jw_imdb_ids:
                logger.debug(f"Found JustWatch ID: {jw_id} for {title} with IMDB ID: {imdb_id}")
                return jw_id, jw_serie_data

        logger.debug(f"Could not find {title} using IMDB ID: {imdb_id}")
        return None, None

    def _find_using_tvdb_id(self, title, sonarr_id, tvdb_id, fast, jw_query_payload={}):
        logger.debug(
            f"Processing title: {title} with Sonarr ID: {sonarr_id} and TVDB ID: {tvdb_id}"
        )

        logger.debug(f"Query JustWatch API with title: {title}")
        jw_query_data = self.justwatch_client.query_title(title, "show", fast, jw_query_payload)

        logger.debug(f"Trying to obtain the TMDB ID using TVDB ID: {tvdb_id} from TMDB API")
        tmdb_id = 0
        tmdb_find_result = self.tmdb.find.find_by_id(tvdb_id, "tvdb_id").get("tv_results", [])
        if tmdb_find_result:
            tmdb_id = int(tmdb_find_result[0].get("id", 0))

        if tmdb_id != 0:
            for entry in jw_query_data["items"]:
                jw_id = entry["id"]
                jw_serie_data, _, jw_tmdb_ids = self._get_jw_serie_data(title, entry)

                if tmdb_id in jw_tmdb_ids:
                    logger.debug(f"Found JustWatch ID: {jw_id} for {title} with TMDB ID: {tmdb_id}")
                    return jw_id, jw_serie_data

        else:
            logger.debug("Could not find a TMDB ID")

        logger.debug(f"Could not find {title} using TVDB ID: {tvdb_id}")
        return None, None

    def _find_serie(self, serie, jw_providers, tmdb_api_key, fast):
        sonarr_id = serie["id"]
        title = serie["title"]
        release_year = serie["year"]
        providers = [values["short_name"] for _, values in jw_providers.items()]

        jw_query_payload = {}
        if fast:
            jw_query_payload = {
                "page_size": 3,
                "release_year_from": release_year,
                "release_year_until": release_year,
                "monetization_types": ["flatrate"],
                "providers": providers,
            }

        imdb_id = serie.get("imdbId", None)
        tvdb_id = serie.get("tvdbId", None)
        logger.debug(f"{title} has IMDB ID: {imdb_id} and TVDB_ID: {tvdb_id}")

        jw_id = None
        jw_serie_data = None

        if tmdb_api_key:
            self.tmdb = pytmdb.TMDB(tmdb_api_key)

        if imdb_id:
            jw_id, jw_serie_data = self._find_using_imdb_id(
                title, sonarr_id, imdb_id, fast, jw_query_payload
            )
            if not jw_serie_data and tvdb_id and tmdb_api_key:
                logger.debug(f"Could not find {title} using IMDB, falling back to TMDB")
                jw_id, jw_serie_data = self._find_using_tvdb_id(title, sonarr_id, tvdb_id, fast)
        elif tvdb_id and tmdb_api_key:
            jw_id, jw_serie_data = self._find_using_tvdb_id(
                title, sonarr_id, tvdb_id, fast, jw_query_payload
            )
        else:
            logger.debug(
                f"No IMDB ID provided by Sonarr and no TMDB configuration set. Skipping serie: {title}"
            )

        return jw_id, jw_serie_data

    def get_series_to_tag(
        self, providers, fast=True, disable_progress=False, tmdb_api_key=None, not_available_tag=None, series_id=None
    ):
        """Find series available on streaming providers and return them with provider names.
        Tags are applied at the series level, so all providers from all episodes are aggregated."""
        tag_series = {}

        if series_id:
            logger.debug(f"Getting series with ID {series_id} from Sonarr")
            sonarr_series = [self.sonarr_client.get_series(id_=series_id)]
        else:
            logger.debug("Getting all the series from Sonarr")
            sonarr_series = self.sonarr_client.get_series()

        raw_jw_providers = self.justwatch_client.get_providers()
        jw_providers = filters.get_providers(raw_jw_providers, providers)
        logger.debug(
            f"Got the following providers: {', '.join([v['clear_name'] for _, v in jw_providers.items()])}"
        )

        progress = Progress(disable=disable_progress)
        with progress:
            for serie in progress.track(sonarr_series):
                sonarr_id = serie["id"]
                title = serie["title"]

                jw_id, jw_serie_data = self._find_serie(
                    serie, jw_providers, tmdb_api_key, fast
                )

                all_providers = set()
                if jw_serie_data:
                    logger.debug(f"Look up season data for {title}")
                    jw_seasons = jw_serie_data.get("seasons", [])

                    for jw_season in jw_seasons:
                        jw_season_id = jw_season["id"]
                        jw_season_data = self.justwatch_client.get_season(jw_season_id)
                        jw_episodes = jw_season_data.get("episodes", [])

                        for episode in jw_episodes:
                            episode_providers = filters.get_jw_providers(episode)

                            providers_match = [
                                provider_details["clear_name"].lower()
                                for provider_id, provider_details in jw_providers.items()
                                if provider_id in episode_providers.keys()
                            ]

                            all_providers.update(providers_match)

                if all_providers:
                    tag_series.update(
                        {
                            sonarr_id: {
                                "title": title,
                                "sonarr_object": serie,
                                "jw_id": jw_id,
                                "providers": sorted(all_providers),
                            }
                        }
                    )

                    logger.debug(
                        f"{title} is streaming on {', '.join(sorted(all_providers))}"
                    )
                elif not_available_tag:
                    tag_series.update(
                        {
                            sonarr_id: {
                                "title": title,
                                "sonarr_object": serie,
                                "jw_id": jw_id,
                                "providers": [not_available_tag],
                            }
                        }
                    )

                    logger.debug(f"{title} is not available on any provider, tagging with '{not_available_tag}'")

        return tag_series

    def tag_series(self, series_with_providers):
        """Add streaming provider tags to series in Sonarr."""
        logger.debug("Starting the tagging process for series")
        self._load_tags()

        for sonarr_id, serie_data in series_with_providers.items():
            serie_obj = serie_data["sonarr_object"]
            title = serie_data["title"]
            provider_names = serie_data["providers"]

            current_tags = set(serie_obj.get("tags", []))

            for provider_name in provider_names:
                tag_id = self._get_or_create_tag(provider_name)
                current_tags.add(tag_id)

            serie_obj["tags"] = list(current_tags)

            try:
                logger.debug(f"Updating tags for serie: {title} (ID: {sonarr_id})")
                self.sonarr_client.upd_series(serie_obj)
            except Exception as e:
                logger.error(f"Failed to update tags for {title}: {e}")

    def get_series_to_clean(
        self, providers, fast=True, disable_progress=False, tmdb_api_key=None, not_available_tag=None, series_id=None
    ):
        """Find series with stale streaming provider tags."""
        clean_series = {}

        if series_id:
            logger.debug(f"Getting series with ID {series_id} from Sonarr")
            sonarr_series = [self.sonarr_client.get_series(id_=series_id)]
        else:
            logger.debug("Getting all the series from Sonarr")
            sonarr_series = self.sonarr_client.get_series()

        # Load tags and build reverse lookup (tag_id -> label)
        self._load_tags()
        tag_id_to_label = {v: k for k, v in self._tag_cache.items()}

        # Build the set of provider tag labels we manage
        raw_jw_providers = self.justwatch_client.get_providers()
        jw_providers = filters.get_providers(raw_jw_providers, providers)
        provider_labels = {v["clear_name"].lower() for _, v in jw_providers.items()}

        # Include not_available_tag as a managed label
        not_available_label = self._sanitize_tag(not_available_tag) if not_available_tag else None
        managed_labels = set(provider_labels)
        if not_available_label:
            managed_labels.add(not_available_label)

        logger.debug(
            f"Got the following providers: {', '.join(provider_labels)}"
        )

        progress = Progress(disable=disable_progress)
        with progress:
            for serie in progress.track(sonarr_series):
                sonarr_id = serie["id"]
                title = serie["title"]
                current_tags = serie.get("tags", [])

                # Find which current tags are managed tags (providers + not_available_tag)
                current_provider_tags = {}
                for tag_id in current_tags:
                    label = tag_id_to_label.get(tag_id)
                    if label and label in managed_labels:
                        current_provider_tags[tag_id] = label

                # Skip if serie has no managed tags
                if not current_provider_tags:
                    continue

                logger.debug(
                    f"Processing title: {title} with Sonarr ID: {sonarr_id}"
                )

                # Find which providers the serie is currently on
                jw_id, jw_serie_data = self._find_serie(
                    serie, jw_providers, tmdb_api_key, fast
                )

                current_jw_providers = set()
                if jw_serie_data:
                    jw_seasons = jw_serie_data.get("seasons", [])

                    for jw_season in jw_seasons:
                        jw_season_id = jw_season["id"]
                        jw_season_data = self.justwatch_client.get_season(jw_season_id)
                        jw_episodes = jw_season_data.get("episodes", [])

                        for episode in jw_episodes:
                            episode_providers = filters.get_jw_providers(episode)

                            providers_match = [
                                provider_details["clear_name"].lower()
                                for provider_id, provider_details in jw_providers.items()
                                if provider_id in episode_providers.keys()
                            ]

                            current_jw_providers.update(providers_match)

                # Find stale tags
                stale_tags = {}
                for tag_id, label in current_provider_tags.items():
                    if label == not_available_label:
                        # not_available_tag is stale if the serie now has providers
                        if current_jw_providers:
                            stale_tags[tag_id] = label
                    else:
                        # Provider tags are stale if no longer on that provider
                        if label not in current_jw_providers:
                            stale_tags[tag_id] = label

                if stale_tags:
                    clean_series.update(
                        {
                            sonarr_id: {
                                "title": title,
                                "sonarr_object": serie,
                                "tags_removed": list(stale_tags.values()),
                                "stale_tag_ids": list(stale_tags.keys()),
                            }
                        }
                    )
                    logger.debug(
                        f"{title} has stale tags: {', '.join(stale_tags.values())}"
                    )

        return clean_series

    def get_series_to_purge_tag(self, tag_label):
        """Find all series that have a specific tag."""
        purge_series = {}

        self._load_tags()
        sanitized = self._sanitize_tag(tag_label)
        tag_id = self._tag_cache.get(sanitized)

        if tag_id is None:
            logger.debug(f"Tag '{sanitized}' does not exist in Sonarr, nothing to purge")
            return purge_series

        logger.debug(f"Looking for series with tag '{sanitized}' (ID: {tag_id})")
        sonarr_series = self.sonarr_client.get_series()

        for serie in sonarr_series:
            if tag_id in serie.get("tags", []):
                sonarr_id = serie["id"]
                purge_series[sonarr_id] = {
                    "title": serie["title"],
                    "sonarr_object": serie,
                    "tags_removed": [sanitized],
                    "stale_tag_ids": [tag_id],
                }

        return purge_series

    def clean_tags(self, series_with_stale_tags):
        """Remove stale streaming provider tags from series in Sonarr."""
        logger.debug("Starting the tag cleanup process for series")

        for sonarr_id, serie_data in series_with_stale_tags.items():
            serie_obj = serie_data["sonarr_object"]
            title = serie_data["title"]
            stale_tag_ids = set(serie_data["stale_tag_ids"])

            current_tags = set(serie_obj.get("tags", []))
            serie_obj["tags"] = list(current_tags - stale_tag_ids)

            try:
                logger.debug(f"Cleaning tags for serie: {title} (ID: {sonarr_id})")
                self.sonarr_client.upd_series(serie_obj)
            except Exception as e:
                logger.error(f"Failed to clean tags for {title}: {e}")
