"""Tests for SCL mask — S1-1.

Verifies that all 6 cloud/invalid classes are correctly excluded
from the Scene Classification Layer mask applied to Sentinel-2 images.
"""

from unittest.mock import MagicMock

from src.infrastructure.earth_engine.image_fetcher import SentinelImageFetcher


class TestSCLMask:
    """S1-1: SCL masking must exclude classes 0, 1, 3, 8, 9, 10."""

    def test_scl_mask_excludes_class_0_no_data(self) -> None:
        """Class 0 (No Data) must be masked — previously missing, biased all indices."""
        image = MagicMock()
        scl = MagicMock()
        image.select.return_value = scl

        # Build chain of neq() calls
        mask_chain = MagicMock()
        scl.neq.return_value = mask_chain
        mask_chain.And.return_value = mask_chain

        SentinelImageFetcher._apply_scl_mask(image)

        # First call must be neq(0) — No Data
        first_neq_call = scl.neq.call_args_list[0]
        assert first_neq_call.args[0] == 0, "Class 0 (No Data) must be the first exclusion"

    def test_scl_mask_excludes_class_1_saturated(self) -> None:
        """Class 1 (Saturated/Defective) must be masked — previously missing."""
        image = MagicMock()
        scl = MagicMock()
        image.select.return_value = scl

        mask_chain = MagicMock()
        scl.neq.return_value = mask_chain
        mask_chain.And.return_value = mask_chain

        SentinelImageFetcher._apply_scl_mask(image)

        excluded_classes = [call.args[0] for call in scl.neq.call_args_list]
        assert 1 in excluded_classes, "Class 1 (Saturated/Defective) must be excluded"

    def test_scl_mask_excludes_all_cloud_classes(self) -> None:
        """All 6 cloud/invalid classes must be present in the mask chain."""
        image = MagicMock()
        scl = MagicMock()
        image.select.return_value = scl

        mask_chain = MagicMock()
        scl.neq.return_value = mask_chain
        mask_chain.And.return_value = mask_chain

        SentinelImageFetcher._apply_scl_mask(image)

        excluded_classes = {call.args[0] for call in scl.neq.call_args_list}
        required_classes = {0, 1, 3, 8, 9, 10}
        assert required_classes == excluded_classes, (
            f"Missing exclusions: {required_classes - excluded_classes}"
        )

    def test_scl_mask_calls_update_mask(self) -> None:
        """The mask must be applied to the image via updateMask()."""
        image = MagicMock()
        scl = MagicMock()
        image.select.return_value = scl

        mask_chain = MagicMock()
        scl.neq.return_value = mask_chain
        mask_chain.And.return_value = mask_chain

        result = SentinelImageFetcher._apply_scl_mask(image)

        image.updateMask.assert_called_once()
        assert result == image.updateMask.return_value
