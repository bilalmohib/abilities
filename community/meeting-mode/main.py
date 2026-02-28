import json
from src.agent.capability import MatchingCapability
from src.main import AgentWorker
from src.agent.capability_worker import CapabilityWorker

    worker: AgentWorker = None

class MeetingModeCapability(MatchingCapability):
    """
    Silent background Meeting Mode.
    Explicit trigger only.
    """

    unique_name: str = "meeting_mode_research"
    matching_hotwords: list[str] = [
        "start meeting mode",
        "begin meeting mode",
    ]

    worker: AgentWorker | None = None
    capability_worker: CapabilityWorker | None = None

    # Do not change following tag of register capability
    #{{register capability}}

    async def meeting_daemon(self):
        """
        Background daemon.
        Must stay alive.
        Must stay silent.
        """
        while True:
            await self.worker.session_tasks.sleep(1)

    def call(self, worker: AgentWorker):
        self.worker = worker
        self.capability_worker = CapabilityWorker(worker)

        # IMPORTANT:
        # Start daemon and DO NOT resume normal flow
        self.worker.session_tasks.create(self.meeting_daemon())