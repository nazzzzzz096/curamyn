from nicegui import ui

def auth_layout(title: str, content_fn):
    with ui.element("div").classes(
        "min-h-screen flex items-center justify-center "
        "bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900"
    ):
        with ui.card().classes("w-[380px] p-8 bg-slate-900 shadow-2xl"):
            ui.label(title).classes(
                "text-2xl font-bold text-white mb-2"
            )
            ui.label("Welcome to Curamyn").classes(
                "text-slate-400 mb-6"
            )
            content_fn()
