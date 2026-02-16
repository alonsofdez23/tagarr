import requests

from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from json import JSONDecodeError

from .exceptions import JustWatchTooManyRequests, JustWatchNotFound, JustWatchBadRequest


class JustWatch(object):
    def __init__(self, locale, ssl_verify=True):
        # Setup base variables
        self.locale_api_url = "https://apis.justwatch.com/content"
        self.graphql_url = "https://apis.justwatch.com/graphql"
        self.ssl_verify = ssl_verify

        # Setup session
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Tagarr"})
        self.session.verify = ssl_verify

        # Setup retries on failure
        retries = Retry(
            total=5,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )

        self.session.mount("http://", HTTPAdapter(max_retries=retries))
        self.session.mount("https://", HTTPAdapter(max_retries=retries))

        # Setup locale by verifying its input
        self.locale = self._get_full_locale(locale)

        # Extract country and language codes for GraphQL queries
        # e.g. "es_ES" -> country="ES", language="es"
        parts = self.locale.split("_")
        self.language = parts[0]
        self.country = parts[1] if len(parts) > 1 else parts[0].upper()

    def __exit__(self, *args):
        self.session.close()

    def _get_full_locale(self, locale):
        default_locale = "en_US"
        url = f"{self.locale_api_url}/locales/state"

        result = self.session.get(url)
        jw_locales = result.json()

        valid_locale = any([True for i in jw_locales if i["full_locale"] == locale])

        # Check if the locale is a iso_3166_2 Country Code
        if not valid_locale:
            locale = "".join([i["full_locale"] for i in jw_locales if i["iso_3166_2"] == locale])

        # If the locale is empty return the default locale
        if not locale:
            return default_locale

        return locale

    def _graphql_query(self, query, variables=None):
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        result = self.session.post(self.graphql_url, json=payload)

        if result.status_code == 400:
            raise JustWatchBadRequest(result.text)
        elif result.status_code == 404:
            raise JustWatchNotFound()
        elif result.status_code == 429:
            raise JustWatchTooManyRequests()

        try:
            data = result.json()
        except JSONDecodeError:
            raise JustWatchBadRequest(result.text)

        if "errors" in data:
            error_msg = data["errors"][0].get("message", "Unknown GraphQL error")
            raise JustWatchBadRequest(error_msg)

        return data.get("data", {})

    def _normalize_id(self, jw_id, prefix):
        """Ensure an ID has the correct prefix for GraphQL (e.g. 'tm', 'ts', 'tss')."""
        jw_id_str = str(jw_id)
        if jw_id_str.startswith(prefix):
            return jw_id_str
        return f"{prefix}{jw_id_str}"

    def get_providers(self):
        query = """
        query GetPackages($country: Country!, $platform: Platform!) {
            packages(country: $country, platform: $platform) {
                packageId
                clearName
                shortName
            }
        }
        """
        variables = {"country": self.country, "platform": "WEB"}
        data = self._graphql_query(query, variables)

        # Transform to legacy format: [{"id": ..., "clear_name": ..., "short_name": ...}]
        return [
            {
                "id": p["packageId"],
                "clear_name": p["clearName"],
                "short_name": p["shortName"],
            }
            for p in data.get("packages", [])
        ]

    def query_title(self, query, content_type, fast=True, result={}, page=1, **kwargs):
        """
        Query JustWatch API to find information about a title

        :query: the title of the show or movie to search for
        :content_type: can either be 'show' or 'movie'. Can also be a list of types.
        """
        if isinstance(content_type, str):
            content_type = content_type.split(",")

        # Map content types to GraphQL objectTypes
        type_map = {"movie": "MOVIE", "show": "SHOW"}
        object_types = [type_map.get(ct, ct.upper()) for ct in content_type]

        page_size = kwargs.get("page_size", 20)

        # Build filter
        gql_filter = {
            "searchQuery": query,
            "objectTypes": object_types,
        }

        # Map legacy kwargs to GraphQL filter
        if "monetization_types" in kwargs:
            monetization_map = {"flatrate": "FLATRATE", "rent": "RENT", "buy": "BUY", "free": "FREE", "ads": "ADS"}
            gql_filter["monetizationTypes"] = [
                monetization_map.get(m, m.upper()) for m in kwargs["monetization_types"]
            ]

        if "providers" in kwargs:
            gql_filter["packages"] = kwargs["providers"]

        if "release_year_from" in kwargs:
            gql_filter["releaseYear"] = {"min": kwargs["release_year_from"]}

        if "release_year_until" in kwargs:
            if "releaseYear" in gql_filter:
                gql_filter["releaseYear"]["max"] = kwargs["release_year_until"]
            else:
                gql_filter["releaseYear"] = {"max": kwargs["release_year_until"]}

        gql_query = """
        query GetPopularTitles(
            $country: Country!,
            $first: Int!,
            $filter: TitleFilter,
            $language: Language!
        ) {
            popularTitles(country: $country, first: $first, filter: $filter) {
                edges {
                    node {
                        id
                        objectType
                        content(country: $country, language: $language) {
                            title
                            originalReleaseYear
                        }
                    }
                }
            }
        }
        """
        variables = {
            "country": self.country,
            "first": page_size,
            "filter": gql_filter,
            "language": self.language,
        }

        data = self._graphql_query(gql_query, variables)

        edges = data.get("popularTitles", {}).get("edges", [])
        items = [{"id": edge["node"]["id"]} for edge in edges]

        return {"items": items, "total_pages": 1}

    def get_movie(self, jw_id):
        node_id = self._normalize_id(jw_id, "tm")

        query = """
        query GetMovie($nodeId: ID!, $country: Country!, $language: Language!) {
            node(id: $nodeId) {
                ... on Movie {
                    id
                    content(country: $country, language: $language) {
                        title
                        externalIds {
                            imdbId
                            tmdbId
                        }
                    }
                    offers(country: $country, platform: WEB) {
                        package {
                            packageId
                            shortName
                        }
                    }
                }
            }
        }
        """
        variables = {
            "nodeId": node_id,
            "country": self.country,
            "language": self.language,
        }

        data = self._graphql_query(query, variables)
        node = data.get("node")

        if not node:
            raise JustWatchNotFound()

        return self._transform_title_data(node)

    def get_show(self, jw_id):
        node_id = self._normalize_id(jw_id, "ts")

        query = """
        query GetShow($nodeId: ID!, $country: Country!, $language: Language!) {
            node(id: $nodeId) {
                ... on Show {
                    id
                    content(country: $country, language: $language) {
                        title
                        externalIds {
                            imdbId
                            tmdbId
                        }
                    }
                    offers(country: $country, platform: WEB) {
                        package {
                            packageId
                            shortName
                        }
                    }
                    seasons {
                        id
                    }
                }
            }
        }
        """
        variables = {
            "nodeId": node_id,
            "country": self.country,
            "language": self.language,
        }

        data = self._graphql_query(query, variables)
        node = data.get("node")

        if not node:
            raise JustWatchNotFound()

        result = self._transform_title_data(node)

        # Transform seasons to legacy format: [{"id": "tss123"}]
        if "seasons" in node and node["seasons"]:
            result["seasons"] = [{"id": s["id"]} for s in node["seasons"]]
        else:
            result["seasons"] = []

        return result

    def get_season(self, jw_id):
        node_id = self._normalize_id(jw_id, "tss")

        query = """
        query GetSeason($nodeId: ID!, $country: Country!, $language: Language!) {
            node(id: $nodeId) {
                ... on Season {
                    id
                    content(country: $country, language: $language) {
                        title
                    }
                    episodes {
                        id
                        offers(country: $country, platform: WEB) {
                            package {
                                packageId
                                shortName
                            }
                        }
                    }
                }
            }
        }
        """
        variables = {
            "nodeId": node_id,
            "country": self.country,
            "language": self.language,
        }

        data = self._graphql_query(query, variables)
        node = data.get("node")

        if not node:
            raise JustWatchNotFound()

        # Transform episodes to legacy format with offers
        episodes = []
        for ep in node.get("episodes", []):
            episode_data = {"id": ep["id"]}
            offers = []
            for offer in ep.get("offers", []):
                pkg = offer.get("package", {})
                offers.append({
                    "provider_id": pkg.get("packageId"),
                    "package_short_name": pkg.get("shortName"),
                })
            if offers:
                episode_data["offers"] = offers
            episodes.append(episode_data)

        return {"episodes": episodes}

    def _transform_title_data(self, node):
        """Transform GraphQL node data to legacy REST format."""
        result = {}

        content = node.get("content", {})

        # Transform external_ids to legacy format
        ext_ids_raw = content.get("externalIds", {})
        if ext_ids_raw:
            external_ids = []
            if ext_ids_raw.get("tmdbId"):
                external_ids.append({"provider": "tmdb", "external_id": str(ext_ids_raw["tmdbId"])})
            if ext_ids_raw.get("imdbId"):
                external_ids.append({"provider": "imdb", "external_id": ext_ids_raw["imdbId"]})
            result["external_ids"] = external_ids
        else:
            result["external_ids"] = []

        # Transform offers to legacy format
        raw_offers = node.get("offers", [])
        if raw_offers:
            offers = []
            for offer in raw_offers:
                pkg = offer.get("package", {})
                offers.append({
                    "provider_id": pkg.get("packageId"),
                    "package_short_name": pkg.get("shortName"),
                })
            result["offers"] = offers

        return result
