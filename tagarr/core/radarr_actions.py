from loguru import logger
from rich.progress import Progress
from pyarr import RadarrAPI

import tagarr.utils.filters as filters

from tagarr.modules.justwatch import JustWatch
from tagarr.modules.justwatch.exceptions import JustWatchNotFound, JustWatchTooManyRequests


class RadarrActions:
    def __init__(self, url, api_key, locale):
        logger.debug(f"Initializing PyRadarr")
        self.radarr_client = RadarrAPI(url, api_key)

        logger.debug(f"Initializing JustWatch API with locale: {locale}")
        self.justwatch_client = JustWatch(locale)

        # Cache for tags: label -> tag_id
        self._tag_cache = {}

    def _load_tags(self):
        """Load all existing tags from Radarr into the cache."""
        logger.debug("Loading existing tags from Radarr")
        tags = self.radarr_client.get_tag()
        self._tag_cache = {tag["label"].lower(): tag["id"] for tag in tags}

    def _get_or_create_tag(self, label):
        """Get a tag ID by label, creating it if it doesn't exist."""
        label = label.lower()

        if label in self._tag_cache:
            return self._tag_cache[label]

        logger.debug(f"Creating new tag: {label}")
        result = self.radarr_client.create_tag(label)
        self._tag_cache[label] = result["id"]
        return result["id"]

    def _get_provider_tag_labels(self):
        """Get the set of all provider tag labels that are managed by Tagarr."""
        return {label for label in self._tag_cache.keys()}

    def _get_jw_movie_data(self, title, jw_entry):
        jw_id = jw_entry["id"]
        jw_movie_data = {}
        jw_tmdb_ids = []

        try:
            logger.debug(f"Querying JustWatch API with ID: {jw_id} for title: {title}")
            jw_movie_data = self.justwatch_client.get_movie(jw_id)

            jw_tmdb_ids = filters.get_tmdb_ids(jw_movie_data.get("external_ids", []))
            logger.debug(f"Got TMDB ID's: {jw_tmdb_ids} from JustWatch API")
        except JustWatchNotFound:
            logger.warning(f"Could not find title: {title} with JustWatch ID: {jw_id}")
        except JustWatchTooManyRequests:
            logger.error(f"JustWatch API returned 'Too Many Requests'")

        return jw_movie_data, jw_tmdb_ids

    def _find_movie(self, movie, jw_providers, fast):
        title = movie["title"]
        tmdb_id = movie["tmdbId"]
        release_year = filters.get_release_date(movie, format="%Y")
        providers = [values["short_name"] for _, values in jw_providers.items()]

        jw_query_payload = {}
        if fast:
            jw_query_payload.update({"page_size": 3})
            jw_query_payload.update(
                {"monetization_types": ["flatrate"], "providers": providers}
            )

            if release_year:
                jw_query_payload.update(
                    {
                        "release_year_from": int(release_year),
                        "release_year_until": int(release_year),
                    }
                )

        logger.debug(f"Query JustWatch API with title: {title}")
        jw_query_data = self.justwatch_client.query_title(title, "movie", fast, **jw_query_payload)

        for entry in jw_query_data["items"]:
            jw_id = entry["id"]
            jw_movie_data, jw_tmdb_ids = self._get_jw_movie_data(title, entry)

            if tmdb_id in jw_tmdb_ids:
                logger.debug(f"Found JustWatch ID: {jw_id} for {title} with TMDB ID: {tmdb_id}")
                return jw_id, jw_movie_data

        return None, None

    def get_movies_to_tag(self, providers, fast=True, disable_progress=False):
        """Find movies available on streaming providers and return them with provider names."""
        tag_movies = {}

        logger.debug("Getting all the movies from Radarr")
        radarr_movies = self.radarr_client.get_movie()

        raw_jw_providers = self.justwatch_client.get_providers()
        jw_providers = filters.get_providers(raw_jw_providers, providers)
        logger.debug(
            f"Got the following providers: {', '.join([v['clear_name'] for _, v in jw_providers.items()])}"
        )

        progress = Progress(disable=disable_progress)
        with progress:
            for movie in progress.track(radarr_movies):
                radarr_id = movie["id"]
                title = movie["title"]
                tmdb_id = movie["tmdbId"]

                logger.debug(
                    f"Processing title: {title} with Radarr ID: {radarr_id} and TMDB ID: {tmdb_id}"
                )

                jw_id, jw_movie_data = self._find_movie(movie, jw_providers, fast)

                if jw_movie_data:
                    movie_providers = filters.get_jw_providers(jw_movie_data)
                    matched_providers = list(set(movie_providers.keys()) & set(jw_providers.keys()))

                    if matched_providers:
                        clear_names = [
                            provider_details["clear_name"].lower()
                            for provider_id, provider_details in jw_providers.items()
                            if provider_id in matched_providers
                        ]

                        tag_movies.update(
                            {
                                radarr_id: {
                                    "title": title,
                                    "radarr_object": movie,
                                    "tmdb_id": tmdb_id,
                                    "jw_id": jw_id,
                                    "providers": clear_names,
                                }
                            }
                        )

                        logger.debug(f"{title} is streaming on {', '.join(clear_names)}")

        return tag_movies

    def tag_movies(self, movies_with_providers):
        """Add streaming provider tags to movies in Radarr."""
        logger.debug("Starting the tagging process for movies")
        self._load_tags()

        for radarr_id, movie_data in movies_with_providers.items():
            movie_obj = movie_data["radarr_object"]
            title = movie_data["title"]
            provider_names = movie_data["providers"]

            current_tags = set(movie_obj.get("tags", []))

            for provider_name in provider_names:
                tag_id = self._get_or_create_tag(provider_name)
                current_tags.add(tag_id)

            movie_obj["tags"] = list(current_tags)

            try:
                logger.debug(f"Updating tags for movie: {title} (ID: {radarr_id})")
                self.radarr_client.upd_movie(movie_obj)
            except Exception as e:
                logger.error(f"Failed to update tags for {title}: {e}")

    def get_movies_to_clean(self, providers, fast=True, disable_progress=False):
        """Find movies with stale streaming provider tags."""
        clean_movies = {}

        logger.debug("Getting all the movies from Radarr")
        radarr_movies = self.radarr_client.get_movie()

        # Load tags and build reverse lookup (tag_id -> label)
        self._load_tags()
        tag_id_to_label = {v: k for k, v in self._tag_cache.items()}

        # Build the set of provider tag labels we manage
        raw_jw_providers = self.justwatch_client.get_providers()
        jw_providers = filters.get_providers(raw_jw_providers, providers)
        provider_labels = {v["clear_name"].lower() for _, v in jw_providers.items()}

        logger.debug(
            f"Got the following providers: {', '.join(provider_labels)}"
        )

        progress = Progress(disable=disable_progress)
        with progress:
            for movie in progress.track(radarr_movies):
                radarr_id = movie["id"]
                title = movie["title"]
                current_tags = movie.get("tags", [])

                # Find which current tags are provider tags
                current_provider_tags = {}
                for tag_id in current_tags:
                    label = tag_id_to_label.get(tag_id)
                    if label and label in provider_labels:
                        current_provider_tags[tag_id] = label

                # Skip if movie has no provider tags
                if not current_provider_tags:
                    continue

                logger.debug(
                    f"Processing title: {title} with Radarr ID: {radarr_id}"
                )

                # Find which providers the movie is currently on
                jw_id, jw_movie_data = self._find_movie(movie, jw_providers, fast)

                current_jw_providers = set()
                if jw_movie_data:
                    movie_providers = filters.get_jw_providers(jw_movie_data)
                    matched_providers = list(set(movie_providers.keys()) & set(jw_providers.keys()))
                    current_jw_providers = {
                        provider_details["clear_name"].lower()
                        for provider_id, provider_details in jw_providers.items()
                        if provider_id in matched_providers
                    }

                # Find stale tags (provider tags that no longer apply)
                stale_tags = {
                    tag_id: label
                    for tag_id, label in current_provider_tags.items()
                    if label not in current_jw_providers
                }

                if stale_tags:
                    clean_movies.update(
                        {
                            radarr_id: {
                                "title": title,
                                "radarr_object": movie,
                                "tags_removed": list(stale_tags.values()),
                                "stale_tag_ids": list(stale_tags.keys()),
                            }
                        }
                    )
                    logger.debug(
                        f"{title} has stale tags: {', '.join(stale_tags.values())}"
                    )

        return clean_movies

    def clean_tags(self, movies_with_stale_tags):
        """Remove stale streaming provider tags from movies in Radarr."""
        logger.debug("Starting the tag cleanup process for movies")

        for radarr_id, movie_data in movies_with_stale_tags.items():
            movie_obj = movie_data["radarr_object"]
            title = movie_data["title"]
            stale_tag_ids = set(movie_data["stale_tag_ids"])

            current_tags = set(movie_obj.get("tags", []))
            movie_obj["tags"] = list(current_tags - stale_tag_ids)

            try:
                logger.debug(f"Cleaning tags for movie: {title} (ID: {radarr_id})")
                self.radarr_client.upd_movie(movie_obj)
            except Exception as e:
                logger.error(f"Failed to clean tags for {title}: {e}")
