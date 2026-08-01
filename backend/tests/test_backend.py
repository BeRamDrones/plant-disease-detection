import unittest
from shapely.geometry import Point, Polygon
from pydantic import ValidationError

from app.models.mission import MissionPhase, MissionStatus
from app.schemas.mission import UTMSSyncMission
from app.schemas.detection import DetectionCreate

class TestProjectJatayuBackend(unittest.TestCase):
    def test_imports(self):
        """Ensure all modules import correctly."""
        try:
            import app.main
            import app.models
            import app.schemas
            import app.crud
            import app.routers
            import app.core.database
            import app.core.config
        except ImportError as e:
            self.fail(f"Failed to import project modules: {e}")

    def test_utms_sync_validation_success(self):
        """Test UTMSSyncMission validations for correct input."""
        valid_payload = {
            "mission_id": 1024,
            "drone_id": "AG-DRONE-001",
            "phase": "survey",
            "status": "in_progress",
            "boundary_points": {
                "type": "Polygon",
                "coordinates": [[[79.088, 21.145], [79.089, 21.145], [79.089, 21.146], [79.088, 21.145]]]
            },
            "crop_class": "wheat"
        }
        mission = UTMSSyncMission(**valid_payload)
        self.assertEqual(mission.mission_id, 1024)
        self.assertEqual(mission.drone_id, "AG-DRONE-001")
        self.assertEqual(mission.phase, MissionPhase.survey)
        self.assertEqual(mission.status, MissionStatus.in_progress)
        self.assertIsNotNone(mission.boundary_points)
        self.assertEqual(mission.boundary_points.type, "Polygon")
        self.assertEqual(mission.crop_class, "wheat")

    def test_utms_sync_validation_invalid_phase(self):
        """Test UTMSSyncMission rejects invalid phase with 422."""
        invalid_payload = {
            "mission_id": 1024,
            "drone_id": "AG-DRONE-001",
            "phase": "invalid_phase",  # Should trigger ValidationError
            "status": "in_progress",
            "boundary_points": None,
            "crop_class": "wheat"
        }
        with self.assertRaises(ValidationError) as context:
            UTMSSyncMission(**invalid_payload)
        self.assertIn("phase", str(context.exception))

    def test_utms_sync_validation_invalid_status(self):
        """Test UTMSSyncMission rejects invalid status with 422."""
        invalid_payload = {
            "mission_id": 1024,
            "drone_id": "AG-DRONE-001",
            "phase": "survey",
            "status": "invalid_status",  # Should trigger ValidationError
            "boundary_points": None,
            "crop_class": "wheat"
        }
        with self.assertRaises(ValidationError) as context:
            UTMSSyncMission(**invalid_payload)
        self.assertIn("status", str(context.exception))

    def test_detection_validation(self):
        """Test DetectionCreate validations and constraints."""
        valid_det = {
            "lat": 21.1455,
            "lon": 79.0885,
            "detected_class": "powdery_mildew",
            "confidence_score": 0.92,
            "image_ref": "/images/frame_001.jpg",
            "model_version": "yolo11m_cls_v2"
        }
        det = DetectionCreate(**valid_det)
        self.assertEqual(det.lat, 21.1455)
        self.assertEqual(det.confidence_score, 0.92)

        # Test out of bounds lat
        invalid_det = valid_det.copy()
        invalid_det["lat"] = 95.0  # Invalid latitude (>90)
        with self.assertRaises(ValidationError):
            DetectionCreate(**invalid_det)

        # Test out of bounds confidence score
        invalid_det2 = valid_det.copy()
        invalid_det2["confidence_score"] = 1.5  # Invalid confidence (>1.0)
        with self.assertRaises(ValidationError):
            DetectionCreate(**invalid_det2)

    def test_shapely_containment(self):
        """Test the core Shapely point-in-polygon containment logic."""
        # Define a polygon zone: grid range (79.088, 21.145) to (79.089, 21.146)
        poly_coords = [(79.088, 21.145), (79.089, 21.145), (79.089, 21.146), (79.088, 21.146), (79.088, 21.145)]
        polygon = Polygon(poly_coords)

        # Point inside: Point(lon, lat)
        pt_inside = Point(79.0885, 21.1455)
        self.assertTrue(polygon.contains(pt_inside))

        # Point outside: Point(lon, lat)
        pt_outside = Point(79.087, 21.144)
        self.assertFalse(polygon.contains(pt_outside))

    def test_inference_pipeline(self):
        """Test that the inference service can be instantiated and runs safely."""
        from app.services.inference import DiseaseDetectionPipeline
        pipeline = DiseaseDetectionPipeline()
        self.assertFalse(pipeline.is_loaded)
        
        # Trigger run_inference (should fall back to mock mode gracefully)
        detections = pipeline.run_inference("dummy_image.jpg")
        # pipeline.is_loaded will be False if PyTorch is installed but the .pt file is missing.
        # We verify that detections are returned successfully.
        self.assertEqual(len(detections), 2)
        self.assertEqual(detections[0]["detected_class"], "powdery_mildew")
        self.assertEqual(detections[1]["detected_class"], "healthy")

if __name__ == '__main__':
    unittest.main()
