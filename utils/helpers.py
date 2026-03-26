from datetime import datetime, timezone
import urllib.parse


def format_date(date_obj):
    """Convert a datetime object to a string in UTC format."
    return date_obj.strftime('%Y-%m-%d %H:%M:%S')


def parse_date(date_string):
    """Parse a date string in UTC format back to a datetime object."
    return datetime.strptime(date_string, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)


def url_encode(data):
    """Encode data for use in a URL."
    return urllib.parse.quote(str(data))


def url_decode(data):
    """Decode a URL-encoded string."
    return urllib.parse.unquote(data)