from rest_framework.pagination import LimitOffsetPagination as DRFLimitOffsetPagination

from core.responses import success_response


class LimitOffsetPagination(DRFLimitOffsetPagination):
    default_limit = 10
    max_limit = 100

    def get_paginated_response(self, data):
        return success_response(
            {
                "count": self.count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            }
        )

