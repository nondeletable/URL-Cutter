import flet as ft

import urlcutter.ui_builders as ui


class FakePage:
    def __init__(self):
        self.title = ""
        self.theme_mode = None
        self.theme = None
        self.scroll = None
        self.window = type(
            "W",
            (),
            {
                "min_width": None,
                "min_height": None,
                "center": lambda self=None: setattr(self, "centered", True),
                "minimized": False,
            },
        )()


def test_configure_window_and_theme_runs_without_errors():
    page = FakePage()
    ui.configure_window_and_theme(page)
    # Проверим, что хотя бы title изменился
    assert page.title == "URL CUTTER"


def test_titlebar_set_main_and_back():
    row, info_button, minimize_button, close_button, drag_area = ui.build_title_bar()

    # отключаем реальный update, чтобы не требовалась привязка к Page
    row.update = lambda: None

    # set_main
    ui.titlebar_set_main(row, info_button, minimize_button, close_button, drag_area)
    assert info_button in row.controls
    assert drag_area in row.controls

    # set_back
    dummy_back = ft.Text("back")
    ui.titlebar_set_back(row, minimize_button, close_button, drag_area, dummy_back)
    assert dummy_back in row.controls
    assert drag_area in row.controls
