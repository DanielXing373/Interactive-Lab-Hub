"""Check that the night shift records text without saving webcam images."""
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


class OvernightPrivacy(unittest.TestCase):
    def test_person_changes_write_only_the_text_log(self):
        script = Path(__file__).with_name("overnight.py").resolve()
        camera = Mock()
        camera.read.side_effect = [(True, object()), (True, object()), KeyboardInterrupt]
        cv2 = Mock()
        cv2.VideoCapture.return_value = camera
        # Preserve the image writer's filesystem effect without a real webcam/OpenCV.
        cv2.imwrite.side_effect = lambda path, frame: Path(path).write_bytes(b"test image")
        pipeline = Mock()
        pipeline.model.predict.return_value = [object()]
        pipeline.interpret.side_effect = ["1 person(s) at left/close", "nobody"]

        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as folder:
            try:
                os.chdir(folder)
                with patch.dict(sys.modules, {"cv2": cv2, "yolo_to_qwen": pipeline}), \
                        patch.object(sys, "argv", [str(script)]), \
                        patch("time.sleep"), contextlib.redirect_stdout(io.StringIO()):
                    result = runpy.run_path(str(script), run_name="__main__")
                result["log"].close()
                entries = [json.loads(line) for line in Path("night_log.jsonl").read_text().splitlines()]
                self.assertEqual([e["reading"] for e in entries if "reading" in e],
                                 ["1 person(s) at left/close", "nobody"])
                self.assertTrue(any(e.get("alive") for e in entries))
                self.assertEqual(sorted(str(p) for p in Path(".").rglob("*")), ["night_log.jsonl"])
                # Saving must also be explicitly off at the model boundary.
                for call in pipeline.model.predict.call_args_list:
                    for option in ("save", "save_txt", "save_crop", "visualize"):
                        self.assertIs(call.kwargs.get(option), False, option)
            finally:
                os.chdir(previous)


if __name__ == "__main__":
    unittest.main()
