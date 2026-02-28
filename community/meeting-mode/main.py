import json
from src.agent.capability import MatchingCapability
from src.main import AgentWorker
from src.agent.capability_worker import CapabilityWorker

class AjsdiosajodasCapability(MatchingCapability):
    worker: AgentWorker = None
    capability_worker: CapabilityWorker = None
    
    # Do not change following tag of register capability
    #{{register capability}}

    async def first_function(self):

        # Resume the normal workflow
        self.capability_worker.resume_normal_flow()

    def call(self, worker: AgentWorker):
        # Initialize the worker and capability worker
        self.worker = worker
        self.capability_worker = CapabilityWorker(self.worker)

        self.worker.session_tasks.create(self.first_function())
