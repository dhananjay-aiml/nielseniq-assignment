import os

from counter.adapters.count_repo import CountInMemoryRepo, CountPostgresRepo
from counter.adapters.object_detector import TFSObjectDetector, FakeObjectDetector
from counter.domain.actions import CountDetectedObjects, PredictObjects


def get_object_detector():
    env = os.environ.get('ENV', 'dev')
    if env == 'dev':
        return FakeObjectDetector()
    if env == 'prod':
        tfs_host = os.environ.get('TFS_HOST', 'localhost')
        tfs_port = os.environ.get('TFS_PORT', 8501)
        model_name = os.environ.get('MODEL_NAME', 'ssd_mobilenet_v2')
        return TFSObjectDetector(tfs_host, tfs_port, model_name)
    raise ValueError(f"Unsupported ENV value: {env}")


def get_object_count_repo():
    env = os.environ.get('ENV', 'dev')
    if env == 'dev':
        return CountInMemoryRepo()
    if env == 'prod':
        dsn = os.environ.get('POSTGRES_DSN')
        if not dsn:
            raise ValueError("POSTGRES_DSN must be set when ENV=prod")
        return CountPostgresRepo(dsn)
    raise ValueError(f"Unsupported ENV value: {env}")


def get_count_action() -> CountDetectedObjects:
    return CountDetectedObjects(get_object_detector(), get_object_count_repo())


def get_prediction_action() -> PredictObjects:
    return PredictObjects(get_object_detector())
