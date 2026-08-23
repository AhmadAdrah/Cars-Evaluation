from math import ceil
from rest_framework.request import Request


DEFAULT_PAGE_SIZE = 12
MAX_PAGE_SIZE = 60


def paginate_queryset(request: Request, queryset, serializer_class, page_size_default: int = DEFAULT_PAGE_SIZE):
    """Slice a queryset into a unified paginated envelope.

    Returns a dict: {count, page, page_size, pages, results}.
    Query params: ?page=<int> (1-based), ?page_size=<int> (capped at MAX_PAGE_SIZE).
    """
    try:
        page = int(request.query_params.get('page', 1))
    except (TypeError, ValueError):
        page = 1
    page = max(1, page)

    try:
        page_size = int(request.query_params.get('page_size', page_size_default))
    except (TypeError, ValueError):
        page_size = page_size_default
    page_size = min(max(1, page_size), MAX_PAGE_SIZE)

    count = queryset.count()
    pages = max(1, ceil(count / page_size))
    if page > pages:
        page = pages

    offset = (page - 1) * page_size
    items = queryset[offset:offset + page_size]

    context = {'request': request}
    return {
        'count': count,
        'page': page,
        'page_size': page_size,
        'pages': pages,
        'results': serializer_class(items, many=True, context=context).data,
    }
