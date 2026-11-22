"""Small, composable agents used by the lead outreach pipeline."""

__all__ = ["PipelineOrchestrator"]


def __getattr__(name):
    if name == "PipelineOrchestrator":
        from .orchestrator import PipelineOrchestrator
        return PipelineOrchestrator
    raise AttributeError(name)
