from __future__ import annotations


MAIN_MENU = {
    "keyboard": [
        [{"text": "状态"}, {"text": "截图"}, {"text": "系统"}],
        [{"text": "历史"}, {"text": "最后一次"}, {"text": "帮助"}],
        [{"text": "工作目录"}, {"text": "监控GPU"}, {"text": "监控CPU"}],
    ],
    "resize_keyboard": True,
    "one_time_keyboard": False,
    "input_field_placeholder": "点按钮，或直接发：运行 python train.py",
}


def menu_text() -> str:
    return (
        "<b>NotifyMe</b>\n\n"
        "可以直接点下面的按钮，也可以发短句：\n"
        "运行 python train.py\n"
        "工作目录 E:\\projects\\my-train\n"
        "在 E:\\projects\\my-train 运行 python train.py\n"
        "监控GPU\n"
        "监控CPU\n"
        "监控文件 output.zip\n"
        "监控端口 127.0.0.1 8000\n"
        "监控网页 http://127.0.0.1:8000/health ok\n"
        "停止 Training"
    )
