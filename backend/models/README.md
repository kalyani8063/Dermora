## Model Files

Keep large local model weights in this folder, but do not commit `.pt` files to normal GitHub history.

Expected local files:

- `backend/models/best.pt`
  Region detector used by `DERMORA_MODEL_PATH`

- `backend/models/acne_type.pt`
  Acne-type detector used by `DERMORA_ACNE_TYPE_MODEL_PATH`

- `backend/models/face_landmarker.task`
  MediaPipe face landmarker model used by `DERMORA_FACE_LANDMARKER_MODEL`

Recommended local `.env` values:

```env
DERMORA_MODEL_PATH=models/best.pt
DERMORA_ACNE_TYPE_MODEL_PATH=models/acne_type.pt
DERMORA_FACE_LANDMARKER_MODEL=backend/models/face_landmarker.task
```

Notes:

- GitHub rejects files larger than 100 MB in normal Git history.
- If you need to share large `.pt` files, use Git LFS or an external storage link.
- This repository intentionally ignores `backend/models/*.pt` so local model files stay out of commits by default.
