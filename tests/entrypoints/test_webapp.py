import io
import json

import pytest

from pathlib import Path
from counter.entrypoints.webapp import create_app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('ENV', 'dev')
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def image_path():
    ref_dir = Path(__file__).parent
    return ref_dir.parent.parent / "resources" / "images" / "boy.jpg"


def test_object_detection(client, image_path):
    # Load the image from the path resource/boy.jpg
    with open(image_path, 'rb') as f:
        image_data = f.read()
    image = io.BytesIO(image_data)

    data = {
        'threshold': '0.9',
        'model_name': 'ssd_mobilenet_v2',
    }
    data['file'] = (image, 'test.jpg')

    # Make a test request to the object_detection endpoint
    response = client.post('/object-count', data = data,
        content_type='multipart/form-data', buffered=True)

    # Check that the count_action was called with the correct arguments and
    # and status code is correct(Integration test)
    assert response.status_code == 200
    assert json.loads(response.data) != None


def test_object_count_end_to_end_accumulates_counts_between_requests(client, image_path):
    responses = []
    for _ in range(2):
        with open(image_path, 'rb') as image_file:
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
        'current_objects': [{'object_class': 'cat', 'count': 1}],
        'total_objects': [{'object_class': 'cat', 'count': 1}],
    }
    assert responses[1].get_json() == {
        'current_objects': [{'object_class': 'cat', 'count': 1}],
        'total_objects': [{'object_class': 'cat', 'count': 2}],
    }


def test_predictions_returns_thresholded_domain_predictions(client, image_path):
    with open(image_path, 'rb') as image_file:
        response = client.post(
            '/predictions',
            data={'threshold': '0.9', 'file': (io.BytesIO(image_file.read()), 'test.jpg')},
            content_type='multipart/form-data',
        )

    assert response.status_code == 200
    assert json.loads(response.data) == [
        {
            'class_name': 'cat',
            'score': 0.999190748,
            'box': {
                'xmin': 0.367288858,
                'ymin': 0.278333426,
                'xmax': 0.735821366,
                'ymax': 0.6988855,
            },
        }
    ]


def test_predictions_returns_empty_list_when_threshold_excludes_all(client, image_path):
    with open(image_path, 'rb') as image_file:
        response = client.post(
            '/predictions',
            data={'threshold': '1.0', 'file': (io.BytesIO(image_file.read()), 'test.jpg')},
            content_type='multipart/form-data',
        )

    assert response.status_code == 200
    assert json.loads(response.data) == []


@pytest.mark.parametrize(
    ('threshold', 'filename', 'image_data'),
    [
        ('not-a-number', 'test.jpg', b'not an image'),
        ('1.1', 'test.jpg', b'not an image'),
        ('0.5', '', b'not an image'),
        ('0.5', 'test.jpg', b'not an image'),
    ],
)
def test_invalid_prediction_requests_return_bad_request(
    client, threshold, filename, image_data
):
    response = client.post(
        '/predictions',
        data={'threshold': threshold, 'file': (io.BytesIO(image_data), filename)},
        content_type='multipart/form-data',
    )

    assert response.status_code == 400
