"""Project 3 regression: colloquial «دهنه» + «N دهنه در راستای L متری» must reach the project-frame prefill."""
from app.application import frame3d_chat_analysis as f3
from app.application.optimization_full.model_resolver import inputs_from_texts
from app.api.routes.optimization_full import _limit_warning

P3 = ("یک سازه ۱۰۰۰ متر در ۲۰۰۰ متر برج ۱۳ طبقه ۱۰۰ دهنه در راستای ۱۰۰۰ متری و ۲۰۰ دهنه در راستای ۲۰۰۰ متری "
      "و روف گاردن هم داشته باشد و باند هلیکوپتر هم باشد")


def test_colloquial_dahaneh_is_frame_request():
    assert f3.is_frame3d_request(P3)


def test_bays_along_length_gives_counts_and_spans():
    i = f3.parse_frame3d_request(P3)
    assert (i.storeys, i.bays_x, i.bays_y, i.bay_x_m, i.bay_y_m) == (13, 100, 200, 10.0, 10.0)
    assert i.pending_bays is None


def test_small_frame_along_length():
    i = f3.parse_frame3d_request("ساختمان ۵ طبقه، ۴ دهانه در جهت ۲۰ متری و ۳ دهانه در جهت ۱۵ متری")
    assert (i.bays_x, i.bay_x_m, i.bays_y, i.bay_y_m) == (4, 5.0, 3, 5.0)


def test_resolver_uses_project_chat_not_defaults():
    ins = inputs_from_texts([P3])
    assert ins and ins["storeys"] == 13 and ins["bays_x"] == 100 and ins["bays_y"] == 200


def test_limit_warning():
    assert _limit_warning({"storeys": 13, "bays_x": 100, "bays_y": 200})
    assert _limit_warning({"storeys": 4, "bays_x": 3, "bays_y": 3}) is None
