import torch

from training.venue_vision_bundle_v6_runtime import VenueVisionBundleV6Runtime


class CountingSegmentationModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.calls = 0
        self.last_shape = None

    def forward(self, inputs):
        self.calls += 1
        self.last_shape = tuple(inputs.shape)
        batch, _channels, height, width = inputs.shape
        logits = torch.zeros((batch, 6, height, width), dtype=inputs.dtype)
        logits[:, 0] = 3.0
        return logits


class UnusedDoorModel(torch.nn.Module):
    def forward(self, _inputs):  # pragma: no cover - not used by this unit test
        raise AssertionError("Door model should not be called")


def test_runtime_segmentation_uses_one_training_sized_cpu_pass():
    segmentation = CountingSegmentationModel()
    runtime = VenueVisionBundleV6Runtime(
        segmentation_model=segmentation,
        door_model=UnusedDoorModel(),
        manifest={
            "model_version": "venue-vision-v6-validation-bundle",
            "runtime_policy": {
                "maximum_reported_confidence": 0.49,
                "door_score_threshold": 0.50,
                "segmentation_canvas_size": 320,
            },
        },
        device=torch.device("cpu"),
    )
    from PIL import Image

    candidates = runtime._segmentation_candidates(
        Image.new("RGB", (1280, 720), (160, 160, 160))
    )

    assert segmentation.calls == 1
    assert segmentation.last_shape == (1, 3, 320, 320)
    assert candidates[0].label == "wall"
