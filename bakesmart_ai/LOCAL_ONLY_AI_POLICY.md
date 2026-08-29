# BakeSmart Local-Only AI Policy

This policy is a hard requirement for the professional 3D/AI rebuild.

## Core rule

BakeSmart must train and run its core AI locally. A hosted AI service must not perform venue understanding, object detection, segmentation, recommendation ranking, scale estimation, cake extraction, scene planning, or 3D generation for the application.

Core models are trained by BakeSmart from random initialization using BakeSmart-controlled datasets and code. Do not download or silently load pretrained model checkpoints for these core models.

## Allowed local tools

- Python
- NumPy
- PyTorch / torchvision as local numerical and training libraries
- OpenCV
- Pillow
- ONNX Runtime for local inference/export validation
- Blender and Blender Python for asset generation/validation
- Local annotation/review tools
- Directly stored or manually downloaded rights-cleared dataset/asset files
- Ordinary non-AI file or metadata retrieval needed to collect rights-cleared public material

Using a library is not the same as outsourcing the model. The weights, labels, training loop, evaluation protocol, geometry rules, and runtime inference remain under BakeSmart control.

## Forbidden for the core pipeline

- Gemini or another hosted model generating training images for future model training
- OpenAI/Anthropic/Google/Roboflow/Replicate or similar hosted inference for labels or predictions
- Remote APIs deciding room geometry, physical scale, obstacles, cake masks, decoration placement, or recommendations
- Auto-labels from a hosted service being treated as ground truth
- Downloaded pretrained checkpoints being presented as a BakeSmart-from-scratch model
- A hidden fallback that sends customer venue/cake photos to an external AI provider

## Legacy synthetic material

Earlier `gemini_synthetic` / `gemini-venue-*` artifacts may remain in repository history for provenance, but they are legacy external synthetic material. They are not eligible for new train, validation, locked-test, or production-accuracy claims under this policy.

## Required checkpoint metadata

New core-model checkpoints/reports must preserve explicit provenance fields equivalent to:

- `pretrained=false`
- `random_initialization=true`
- `external_ai_provider=null`
- dataset version/checksum
- train/validation/test split identifiers
- locked-test usage state

## Scale rule

Physical size is not learned from visual appearance alone. Scale comes from customer-confirmed measurements and calibration. ML may propose semantic regions; deterministic geometry and constraint code converts verified measurements to metres.

## Branch rule

All implementation work for this rebuild is performed on `Sana's-work`. The `main` branch is not a development target for this work.
