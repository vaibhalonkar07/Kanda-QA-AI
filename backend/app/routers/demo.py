from fastapi import APIRouter, Response

from ..services.vision.synthetic import MARKER_MM, render_jpeg

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.get("/sample-image.jpg")
def sample_image(seed: int = 0):
    """Synthetic 15-onion tray with a 40 mm ArUco marker, for trying the pipeline without a camera."""
    return Response(render_jpeg(seed), media_type="image/jpeg", headers={"X-Marker-Size-Mm": str(MARKER_MM)})
