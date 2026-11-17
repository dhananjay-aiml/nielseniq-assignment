# NIQ Innovation Enablement - Object Counter Challenge

The goal of this repo is demonstrate how to apply Hexagonal Architecture in a ML based system.

This application consists in a Flask API that receives an image and a threshold and returns the number of objects detected in the image.

The application is composed of three layers:

- **entrypoints**: Exposes the API and receives the requests. It is also responsible for validating the requests and returning the responses.

- **adapters**: Communicates with external services. It is responsible for translating the domain objects to the external services objects and vice-versa.

- **domain**: Business logic. It is responsible for orchestrating the calls to the external services and for applying the business rules.

The model used in this example has been taken from 
[Kaggle](https://www.kaggle.com/models/google/mobilenet-v2/tensorFlow1/openimages-v4-ssd-mobilenet-v2/1)


## Instructions to setup the model (Unix)
```bash
mkdir -p tmp/model/ssd_mobilenet_v2/1
curl -L -o tmp/model.tar.gz \
  http://download.tensorflow.org/models/object_detection/ssd_mobilenet_v2_coco_2018_03_29.tar.gz
tar -xzvf tmp/model.tar.gz -C tmp/model
mv \
    tmp/model/ssd_mobilenet_v2_coco_2018_03_29/saved_model/saved_model.pb \
    tmp/model/ssd_mobilenet_v2/1
chmod -R 777 tmp/model
rm tmp/model.tar.gz
rm -rf tmp/model/ssd_mobilenet_v2_coco_2018_03_29
```

By the end you should have the following structure:
 ```
 tmp/
  model/
    ssd_mobilenet_v2/
        1/
        saved_model.pb
 ```

## Setup and run Tensorflow Serving

### For unix systems
```bash
num_physical_cores=$(lscpu --all --parse=SOCKET,CORE | grep -v '^#' | uniq | wc -l)

docker run --rm -d \
    --name=tfserving \
    -p 8501:8501 \
    --mount type=bind,source=$(pwd)/tmp/model,target=/models \
    -e OMP_NUM_THREADS=$num_physical_cores \
    -e TENSORFLOW_INTRA_OP_PARALLELISM=$num_physical_cores \
    -e MODEL_NAME=ssd_mobilenet_v2 \
    tensorflow/serving
```

### For Windows (Powershell)
```powershell
$num_physical_cores=(Get-WmiObject Win32_Processor | Select-Object NumberOfCores).NumberOfCores

docker run --rm -d `
    --name=tfserving `
    -p 8501:8501 `
    -v "$pwd\tmp\model:/models" `
    -e OMP_NUM_THREADS=$num_physical_cores `
    -e TENSORFLOW_INTRA_OP_PARALLELISM=$num_physical_cores `
    -e MODEL_NAME=ssd_mobilenet_v2 `
    tensorflow/serving
```

## Running PostgreSQL

```bash
docker run --rm --name object-counter-postgres \
-e POSTGRES_DB=prod_counter \
-e POSTGRES_USER=counter \
-e POSTGRES_PASSWORD=counter \
-p 5432:5432 -d postgres:16
```

PowerShell:
```powershell
docker run --rm --name object-counter-postgres `
-e POSTGRES_DB=prod_counter `
-e POSTGRES_USER=counter `
-e POSTGRES_PASSWORD=counter `
-p 5432:5432 -d postgres:16
```

For production mode, configure the database connection string:

Unix:
```bash
export POSTGRES_DSN="host=localhost port=5432 dbname=prod_counter user=counter password=counter"
```

PowerShell:
```powershell
$env:POSTGRES_DSN = "host=localhost port=5432 dbname=prod_counter user=counter password=counter"
```

## Setup virtualenv (Python >= 3.10)

Unix:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=.
```

Powershell:
```powershell
python3 -m venv .venv
.venv\scripts\Activate.ps1
pip install -r requirements.txt
$Env:PYTHONPATH = "."
```


## Run the application

### Using fakes
```bash
python -m counter.entrypoints.webapp
```

### Using real services in docker containers

Unix
```bash
ENV=prod python -m counter.entrypoints.webapp
```
Powershell: 
```powershell
$env:ENV = "prod"
python -m counter.entrypoints.webapp
```

## Call the service

```bash
 curl -F "threshold=0.9" -F "file=@resources/images/boy.jpg" http://localhost:5000/object-count
 curl -F "threshold=0.9" -F "file=@resources/images/cat.jpg" http://localhost:5000/object-count
 curl -F "threshold=0.9" -F "file=@resources/images/food.jpg" http://localhost:5000/object-count 
```

To get the detections rather than their per-class counts:
```bash
curl -F "threshold=0.9" -F "file=@resources/images/boy.jpg" http://localhost:5000/predictions
```

The `/predictions` response is a JSON list of predictions, each with `class_name`,
`score`, and a normalized `box` containing `xmin`, `ymin`, `xmax`, and `ymax`.
Both endpoints return HTTP 400 for missing, empty, or invalid image uploads and
thresholds outside the inclusive range 0–1.

> [!TIP]
> If you face service connectivity issues on Windows, try replacing "localhost" with "127.0.0.1" globally

## Run the tests

```
pytest
```

The entrypoint tests exercise the Flask request flow with the development fake
detector and in-memory counter. They do not require TensorFlow Serving or
PostgreSQL. The object-count end-to-end test submits two image requests and
checks that the response reflects the updated cumulative count.

### PostgreSQL integration test

The integration test submits requests through Flask and verifies that counts
are persisted by the PostgreSQL adapter. It uses a deterministic detector, so
TensorFlow Serving is not required. Run it only against a disposable test
database, never a production database:

```powershell
docker run --rm --name object-counter-test-postgres `
  -e POSTGRES_DB=object_counter_test `
  -e POSTGRES_USER=counter `
  -e POSTGRES_PASSWORD=counter `
  -p 5433:5432 -d postgres:16

$env:POSTGRES_TEST_DSN = "host=127.0.0.1 port=5433 dbname=object_counter_test user=counter password=counter"
python -m pytest -m integration
docker stop object-counter-test-postgres
```

Without `POSTGRES_TEST_DSN`, the integration test is skipped when running the
regular test suite. It creates a unique object class per run and removes only
that test row afterward.