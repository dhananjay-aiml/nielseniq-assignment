import io
import os
from pathlib import Path
from uuid import uuid4

import pytest

from counter.adapters.count_repo import CountPostgresRepo
from counter.domain.actions import CountDetectedObjects, PredictObjects
from counter.domain.models import Box, ObjectCount, Prediction
from counter.entrypoints import webapp


@pytest.fixture
def postgres_test_config():
    dsn = os.environ.get('POSTGRES_TEST_DSN')
    if not dsn:
        pytest.skip('Set POSTGRES_TEST_DSN to run PostgreSQL integration tests')

    try:
        import psycopg
    except ImportError:
        pytest.skip('Install project requirements to run PostgreSQL integration tests')

    return dsn, psycopg


@pytest.fixture
def object_class(postgres_test_config):
    dsn, psycopg = postgres_test_config
    CountPostgresRepo(dsn)
    class_name = f'integration-{uuid4().hex}'
    yield class_name

    with psycopg.connect(dsn) as connection:
        connection.execute(
            'DELETE FROM object_counts WHERE object_class = %s',
            (class_name,),
        )


@pytest.mark.integration
def test_object_count_endpoint_persists_counts_in_postgres(
    monkeypatch, postgres_test_config, object_class
):
    dsn, _ = postgres_test_config
    repository = CountPostgresRepo(dsn)

    class IntegrationDetector:
        def predict(self, image):
            return [
                Prediction(
                    class_name=object_class,
                    score=0.95,
                    box=Box(xmin=0.1, ymin=0.1, xmax=0.9, ymax=0.9),
                )
            ]

    detector = IntegrationDetector()
    count_action = CountDetectedObjects(detector, repository)
    monkeypatch.setattr(webapp.config, 'get_count_action', lambda: count_action)
    monkeypatch.setattr(
        webapp.config,
        'get_prediction_action',
        lambda: PredictObjects(detector),
    )

    app = webapp.create_app()
    app.config['TESTING'] = True
    image_path = Path(__file__).parents[2] / 'resources' / 'images' / 'boy.jpg'

    with app.test_client() as client:
        responses = []
        for _ in range(2):
            with image_path.open('rb') as image_file:
                response = client.post(
                    '/object-count',
                    data={
                        'threshold': '0.9',
                        'file': (io.BytesIO(image_file.read()), 'test.jpg'),
                    },
                    content_type='multipart/form-data',
                )
            responses.append(response)

    assert [response.status_code for response in responses] == [200, 200]
    assert responses[0].get_json() == {
        'current_objects': [{'object_class': object_class, 'count': 1}],
        'total_objects': [{'object_class': object_class, 'count': 1}],
    }
    assert responses[1].get_json() == {
        'current_objects': [{'object_class': object_class, 'count': 1}],
        'total_objects': [{'object_class': object_class, 'count': 2}],
    }

    reopened_repository = CountPostgresRepo(dsn)
    assert reopened_repository.read_values([object_class]) == [
        ObjectCount(object_class, 2)
    ]
