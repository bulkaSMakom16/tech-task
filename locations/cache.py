from hashlib import sha256
from uuid import uuid4

from django.core.cache import cache


LIST_VERSION_KEY = "locations:list:version"


def location_list_cache_key(request):
    new_version = uuid4().hex
    version = cache.get_or_set(LIST_VERSION_KEY, new_version, timeout=None)
    url = request.build_absolute_uri()
    url_hash = sha256(url.encode("utf-8")).hexdigest()
    return f"locations:list:{version}:{url_hash}"


def clear_location_list_cache():
    cache.delete(LIST_VERSION_KEY)
