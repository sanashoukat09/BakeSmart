from training.train_real_venue_door_detector_v5 import DOOR_PROFILE


def test_door_profile_uses_correct_class_and_minimum_scene_guard():
    assert DOOR_PROFILE.class_id == 2
    assert DOOR_PROFILE.class_key == "door"
    assert DOOR_PROFILE.minimum_training_scenes == 5
