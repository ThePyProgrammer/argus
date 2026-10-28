import numpy as np

from scripts.boxer_worker import _source_bbox


def test_square_model_coordinates_return_to_non_square_camera_pixels():
    box = np.array([96., 384., 192., 864.])  # x1,x2,y1,y2 in 960x960
    np.testing.assert_allclose(_source_bbox(box, 320, 240, 960), [32, 48, 128, 216])
    np.testing.assert_array_equal(box, [96, 384, 192, 864])


def test_full_model_image_maps_to_full_camera_image():
    np.testing.assert_allclose(_source_bbox([0, 960, 0, 960], 320, 240, 960), [0, 0, 320, 240])
