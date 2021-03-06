import logging

from dynamo.web.modules._base import WebModule
from dynamo.web.modules.request.mixin import ParseInputMixin
from dynamo.request.deletion import DeletionRequestManager
import dynamo.dataformat as df
from dynamo.dataformat.request import Request

LOG = logging.getLogger(__name__)

class DeletionRequestBase(WebModule, ParseInputMixin):
    def __init__(self, config):
        WebModule.__init__(self, config)
        ParseInputMixin.__init__(self, config)

        self.manager = DeletionRequestManager()


class MakeDeletionRequest(DeletionRequestBase):
    def __init__(self, config):
        DeletionRequestBase.__init__(self, config)
        self.must_authenticate = True

    def run(self, caller, request, inventory):
        self.parse_input(request, inventory, ('item', 'site'), ('item', 'site'))

        self.manager.lock()

        try:
            constraints = self.make_constraints(by_id = False)
            existing_requests = self.manager.get_requests(**constraints)

            existing = None

            for request_id in sorted(existing_requests.iterkeys()):
                if existing_requests[request_id].status == Request.ST_NEW:
                    existing = existing_requests[request_id]
                    break
                elif existing_requests[request_id].status == Request.ST_ACTIVATED:
                    existing = existing_requests[request_id]

            if existing is not None:
                return [existing.to_dict()]

            else:
                request = self.manager.create_request(caller, self.params['item'], self.params['site'])
                return [request.to_dict()]

        finally:
            self.manager.unlock()


class PollDeletionRequest(DeletionRequestBase):
    def run(self, caller, request, inventory):
        self.parse_input(request, inventory, ('request_id', 'item', 'site', 'status', 'user'))
    
        constraints = self.make_constraints(by_id = False)
        existing_requests = self.manager.get_requests(**constraints)

        if 'item' in self.params and 'site' in self.params and \
                ('all' not in self.params or not self.params['all']):
            # this was a query by item and site - if show-all is not requested, default to showing the latest
            max_id = max(existing_requests.iterkeys())
            existing_requests = {max_id: existing_requests[max_id]}

        return [r.to_dict() for r in existing_requests.itervalues()]


export_data = {
    'delete': MakeDeletionRequest,
    'polldelete': PollDeletionRequest
}
