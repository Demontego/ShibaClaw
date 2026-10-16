import pytest

from shibaclaw.automation.grants import job_is_approved, operation_fingerprint
from shibaclaw.automation.service import AutomationService
from shibaclaw.automation.types import AutomationJob, AutomationPayload, AutomationSchedule


# Produced by the pre-model fingerprint algorithm for this persisted one-shot.
LEGACY_FINGERPRINT = "0ce6f69fc2dd4adb"


def legacy_job():
    return AutomationJob(
        id="legacy-job",
        name="Legacy job",
        schedule=AutomationSchedule(kind="at", at_ms=2000000000000),
        payload=AutomationPayload(message="Legacy approval"),
        require_approval=True,
        approved_fingerprint=LEGACY_FINGERPRINT,
    )


@pytest.mark.parametrize("model", [None, ""])
def test_default_model_preserves_legacy_approval(model):
    job = legacy_job()
    job.payload.model = model
    assert operation_fingerprint(job.schedule, job.payload) == LEGACY_FINGERPRINT
    assert job_is_approved(job)


def test_changing_explicit_model_requires_new_approval():
    job = legacy_job()
    job.payload.model = "openai/gpt-4.1"
    assert not job_is_approved(job)
    job.approved_fingerprint = operation_fingerprint(job.schedule, job.payload)
    assert job_is_approved(job)
    job.payload.model = "openai/gpt-4.1-mini"
    assert not job_is_approved(job)
    job.payload.model = None
    assert not job_is_approved(job)


@pytest.mark.asyncio
async def test_persisted_legacy_one_shot_executes_with_existing_approval(tmp_path):
    executed = []

    async def on_scheduled(job):
        executed.append(job.id)

    service = AutomationService(
        store_path=tmp_path / "automation.json", workspace=tmp_path,
        on_scheduled=on_scheduled,
    )
    persisted = service._job_to_dict(legacy_job())
    persisted["payload"].pop("model")
    job = service._job_from_dict(persisted)
    await service._execute(job)
    assert executed == ["legacy-job"]
    assert job.state.last_status == "ok"
    assert job.state.last_error == ""
