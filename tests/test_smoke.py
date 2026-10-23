import seatmap
from seatmap.pipeline import STAGES
from seatmap.runs import STAGE_DIRS


def test_version() -> None:
    assert seatmap.__version__ == "0.1.0"


def test_every_stage_has_an_output_folder() -> None:
    assert list(STAGES) == list(STAGE_DIRS)
