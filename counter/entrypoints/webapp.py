from io import BytesIO
import math

from flask import Flask, request, jsonify
from PIL import Image, UnidentifiedImageError

from counter import config

def create_app():
    app = Flask(__name__)

    count_action = config.get_count_action()
    prediction_action = config.get_prediction_action()

    def parse_image_request():
        threshold_value = request.form.get('threshold', '0.5')
        try:
            threshold = float(threshold_value)
        except (TypeError, ValueError):
            return None, None, (jsonify(error="threshold must be a number between 0 and 1"), 400)
        if not math.isfinite(threshold) or not 0 <= threshold <= 1:
            return None, None, (jsonify(error="threshold must be a number between 0 and 1"), 400)

        uploaded_file = request.files.get('file')
        if uploaded_file is None or not uploaded_file.filename:
            return None, None, (jsonify(error="file is required"), 400)

        image = BytesIO(uploaded_file.read())
        if not image.getbuffer().nbytes:
            return None, None, (jsonify(error="file must not be empty"), 400)
        try:
            with Image.open(image) as decoded_image:
                decoded_image.verify()
        except (UnidentifiedImageError, OSError):
            return None, None, (jsonify(error="file must contain a valid image"), 400)
        image.seek(0)
        return image, threshold, None

    @app.route('/object-count', methods=['POST'])
    def object_detection():
        image, threshold, error = parse_image_request()
        if error:
            return error
        count_response = count_action.execute(image, threshold)
        return jsonify(count_response)

    @app.route('/predictions', methods=['POST'])
    def object_predictions():
        image, threshold, error = parse_image_request()
        if error:
            return error
        predictions = prediction_action.execute(image, threshold)
        return jsonify(predictions)

    return app

if __name__ == '__main__':
    app = create_app()
    app.run('0.0.0.0', debug=True)
