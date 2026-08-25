from training.train_real_venue_door_detector_v6 import DOOR_PROFILE_V6
from training.resume_real_venue_door_detector_v6 import CHECKPOINT


def test_v6_door_profile_requires_correction_and_adaptive_fine_tuning():
    assert DOOR_PROFILE_V6.class_id == 2
    assert DOOR_PROFILE_V6.adaptive_fine_tuning is True
    assert DOOR_PROFILE_V6.forbidden_positive_scene_ids == ("real-venue-0038",)


def test_v6_resume_uses_the_v6_best_checkpoint():
    assert CHECKPOINT.as_posix().endswith(
        "models/venue_vision_door_detector_v6/best_model.pt"
    )
