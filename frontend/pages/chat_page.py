from nicegui import ui
import asyncio

from frontend.state.app_state import state
from frontend.api.upload_client import send_ai_interaction
from frontend.api.consent_client import update_consent
from frontend.api.memory_client import delete_memory
from frontend.api.auth_client import logout_user
from frontend.api.chat_history_client import fetch_chat_history

# =================================================
# GLOBAL STATE (NO UI OBJECTS)
# =================================================
CHAT_CONTAINER = None
UPLOAD_WIDGET = None

CURRENT_MODE = "text"
CURRENT_IMAGE_TYPE = None
PENDING_FILE_BYTES = None

CONSENT_MENU = None
DELETE_DIALOG = None

# =================================================
# MAIN PAGE
# =================================================
def show_chat_page():
    global CHAT_CONTAINER, CONSENT_MENU, DELETE_DIALOG

    ui.dark_mode().enable()

    # ================= DELETE MEMORY DIALOG =================
    DELETE_DIALOG = ui.dialog()
    with DELETE_DIALOG:
        ui.label("Delete memory?")
        with ui.row().classes("gap-4"):
            ui.button("Cancel", on_click=lambda: DELETE_DIALOG.close())
            ui.button("Delete", on_click=_handle_confirm_delete)

    # ================= PAGE LAYOUT =================
    with ui.column().classes("h-screen w-full overflow-hidden"):

        # ---------- HEADER ----------
        with ui.row().classes(
            "w-full px-6 py-3 bg-[#0b1220] justify-between items-center shrink-0"
        ):
            ui.label("Curamyn").classes("text-xl font-bold text-white")
            with ui.row().classes("gap-3"):
                CONSENT_MENU = _render_consent_menu()
                ui.button("DELETE MEMORY", on_click=_open_delete_dialog)
                ui.button("LOGOUT", on_click=_logout)

        # ---------- CHAT AREA ----------
        with ui.element("div").classes(
            "flex-1 w-full overflow-y-auto chat-scroll"
        ):
            CHAT_CONTAINER = ui.column().classes(
                "w-full max-w-6xl mx-auto px-6 py-6 gap-3"
            )

            # ✅ LOAD CHAT HISTORY FROM BACKEND
            if state.token and state.session_id:
                try:
                    messages = fetch_chat_history(
                        token=state.token,
                        session_id=state.session_id,
                    )

                    if messages:
                        state.messages = messages
                        for m in messages:
                            _render_message(m)
                    else:
                        _add_ai("Hi 👋 How can I help you today?")

                except Exception as e:
                    print("HISTORY LOAD ERROR:", e)
                    _add_ai("Hi 👋 How can I help you today?")
            else:
                _add_ai("Hi 👋 How can I help you today?")

        # ---------- INPUT BAR ----------
        _render_input_bar()

# =================================================
# DELETE MEMORY
# =================================================
def _open_delete_dialog():
    if DELETE_DIALOG:
        DELETE_DIALOG.open()

def _handle_confirm_delete():
    if DELETE_DIALOG:
        DELETE_DIALOG.close()
    _do_delete()

def _do_delete():
    async def task():
        try:
            await asyncio.to_thread(delete_memory)
            state.messages.clear()
            state.session_id = None
            CHAT_CONTAINER.clear()
            _clear_browser_chat()
            _add_ai("🧹 Memory cleared. How can I help you now?")
            ui.notify("Memory deleted successfully", type="positive")
        except Exception as e:
            ui.notify(str(e), type="negative")

    asyncio.create_task(task())

# =================================================
# CONSENT MENU
# =================================================
def _render_consent_menu():
    with ui.menu() as menu:
        ui.label("Consent Preferences").classes("font-semibold")

        mem = ui.checkbox("Allow memory", value=state.consent["memory"])
        img = ui.checkbox("Allow images", value=state.consent["image"])
        doc = ui.checkbox("Allow documents", value=state.consent["document"])

        def save():
            new = {
                "memory": mem.value,
                "image": img.value,
                "document": doc.value,
                "voice": state.consent.get("voice", False),
            }
            update_consent(state.token, new)
            state.consent = new
            ui.notify("Consent updated", type="positive")
            menu.close()

        ui.button("SAVE", on_click=save)

    btn = ui.button("CONSENT")
    btn.on_click(menu.open)
    return menu

# =================================================
# INPUT BAR
# =================================================
def _render_input_bar():
    global UPLOAD_WIDGET

    with ui.element("div").classes(
        "w-full bg-[#0b1220] border-t border-gray-800 p-4 shrink-0"
    ):
        with ui.row().classes("max-w-4xl mx-auto items-center gap-2"):

            with ui.menu() as type_menu:
                ui.menu_item("Text", on_click=_set_text_mode)
                ui.menu_item("X-ray", on_click=lambda: _set_image_mode("xray"))
                ui.menu_item("Skin", on_click=lambda: _set_image_mode("skin"))
                ui.menu_item("Document", on_click=_set_document_mode)

            ui.button("+ TYPE", on_click=type_menu.open)

            UPLOAD_WIDGET = ui.upload(
                auto_upload=True,
                on_upload=_on_file_selected,
            ).props("accept=*/*")

            input_box = ui.input("Message Curamyn...").classes("flex-1")
            ui.button("➤", on_click=lambda: _send(input_box))
            ui.menu_item("Voice", on_click=_set_audio_mode)
            record_btn = ui.button("🎤 Record", on_click=_start_recording)
            stop_btn = ui.button("🛑 Stop", on_click=_stop_recording)


def _start_recording():
    ui.run_javascript("""
    window.audioChunks = [];
    navigator.mediaDevices.getUserMedia({ audio: true })
      .then(stream => {
        window.mediaRecorder = new MediaRecorder(stream);
        mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
        mediaRecorder.start();
      });
    """)


def _stop_recording():
    ui.run_javascript("""
    mediaRecorder.stop();
    mediaRecorder.onstop = async () => {
        const blob = new Blob(audioChunks, { type: 'audio/webm' });
        const arrayBuffer = await blob.arrayBuffer();
        window.voiceData = Array.from(new Uint8Array(arrayBuffer));
    };
    """)

async def _send_audio():
    if not hasattr(ui.context.client, "voiceData"):
        ui.notify("No audio captured", type="warning")
        return

    audio_bytes = bytes(ui.context.client.voiceData)

    response = await asyncio.to_thread(
        send_ai_interaction,
        token=state.token,
        session_id=state.session_id,
        input_type="audio",
        response_mode="voice",
        audio_bytes=audio_bytes,
    )

    state.session_id = response.get("session_id", state.session_id)

    audio_base64 = response.get("audio")
    if audio_base64:
        _play_audio(audio_base64)

# =================================================
# MODE
# =================================================
def _set_audio_mode():
    global CURRENT_MODE
    CURRENT_MODE = "audio"

def _set_text_mode():
    global CURRENT_MODE, CURRENT_IMAGE_TYPE, PENDING_FILE_BYTES
    CURRENT_MODE = "text"
    CURRENT_IMAGE_TYPE = None
    PENDING_FILE_BYTES = None

def _set_image_mode(img_type):
    global CURRENT_MODE, CURRENT_IMAGE_TYPE
    CURRENT_MODE = "image"
    CURRENT_IMAGE_TYPE = img_type

def _set_document_mode():
    global CURRENT_MODE, CURRENT_IMAGE_TYPE
    CURRENT_MODE = "document"
    CURRENT_IMAGE_TYPE = "document"

# =================================================
# FILE UPLOAD
# =================================================
async def _on_file_selected(event):
    global PENDING_FILE_BYTES

    PENDING_FILE_BYTES = await event.file.read()

    import base64, mimetypes
    mime, _ = mimetypes.guess_type(event.file.name)
    mime = mime or "image/png"

    encoded = base64.b64encode(PENDING_FILE_BYTES).decode()
    data_url = f"data:{mime};base64,{encoded}"

    msg = {
        "author": "You",
        "sent": True,
        "type": "image",
        "data": data_url,
    }

    state.messages.append(msg)

    with CHAT_CONTAINER:
        with ui.row().classes("w-full justify-end"):
            ui.image(data_url).classes("max-w-xs rounded-lg border border-gray-600")

    _store_message_js(msg)
    _scroll_to_bottom()


# =================================================
# SEND
# =================================================
async def _send(input_box):
    global PENDING_FILE_BYTES

    if CURRENT_MODE == "text":
        text = input_box.value.strip()
        if not text:
            return
        input_box.value = ""
        _add_user(text)
        await _send_text(text)
        return

    if not PENDING_FILE_BYTES:
        ui.notify("Select a file first", type="warning")
        return

    await _send_file()

async def _send_text(text):
    response = await asyncio.to_thread(
        send_ai_interaction,
        token=state.token,
        session_id=state.session_id,
        input_type="text",
        text=text,
    )

    message = response.get("response_text") or response.get("message")
    state.session_id = response.get("session_id", state.session_id)

    _add_ai(message)

async def _send_file():
    global PENDING_FILE_BYTES

    response = await asyncio.to_thread(
        send_ai_interaction,
        token=state.token,
        input_type="image",
        session_id=state.session_id,
        image_type=CURRENT_IMAGE_TYPE,
        file_bytes=PENDING_FILE_BYTES,
    )

    text = response.get("response_text") or response.get("message")
    disclaimer = response.get("disclaimer")

    state.session_id = response.get("session_id", state.session_id)

    if text:
        _add_ai(text)
    if disclaimer:
        _add_ai(f"⚠️ {disclaimer}")

    PENDING_FILE_BYTES = None
    UPLOAD_WIDGET.reset()

# =================================================
# CHAT UI + BROWSER SESSION STORAGE
# =================================================
def _add_user(text):
    msg = {"author": "You", "text": text, "sent": True}
    state.messages.append(msg)

    with CHAT_CONTAINER:
        bubble = ui.chat_message(
            text=text,
            name="You",
            sent=True,        # ✅ RIGHT SIDE
        )

        # 🔹 Remove bubble look, keep text only
        bubble.classes(
            "bg-transparent text-white shadow-none"
        )

    _store_message_js(msg)
    _scroll_to_bottom()


def _add_ai(text):
    msg = {"author": "Curamyn", "text": text, "sent": False}
    state.messages.append(msg)

    with CHAT_CONTAINER:
        ui.chat_message(
            text=text,
            name="Curamyn",
            sent=False,
        )

    _store_message_js(msg)
    _scroll_to_bottom()


def _render_message(m):
    with CHAT_CONTAINER:
        bubble = ui.chat_message(
            text=m.get("text", ""),
            name=m.get("author", ""),
            sent=m.get("sent", False),
        )

        if m.get("sent"):
            bubble.classes(
                "bg-transparent text-white shadow-none"
            )



        
def _store_message_js(msg):
    ui.run_javascript(f"""
        (function() {{
            const existing = JSON.parse(
                sessionStorage.getItem('chat_messages') || '[]'
            );

            existing.push({msg});

            sessionStorage.setItem(
                'chat_messages',
                JSON.stringify(existing)
            );

            window.chatMessages = existing;
        }})();
    """)

def _clear_browser_chat():
    ui.run_javascript("sessionStorage.removeItem('chat_messages');")

# =================================================
# SCROLL
# =================================================
def _scroll_to_bottom():
    ui.run_javascript("""
        setTimeout(() => {
            const el = document.querySelector('.chat-scroll');
            if (el) {
                el.scrollTo({
                    top: el.scrollHeight,
                    behavior: 'smooth'
                });
            }
        }, 50);
    """)

# =================================================
# LOGOUT
# =================================================
def _logout():
    if state.token and state.session_id:
        try:
            from frontend.api.chat_history_client import end_chat_session
            end_chat_session(
                token=state.token,
                session_id=state.session_id,
            )
        except Exception as e:
            print("END SESSION ERROR:", e)

    _clear_browser_chat()

    if CONSENT_MENU:
        CONSENT_MENU.close()

    try:
        if state.token and state.session_id:
            logout_user(
                token=state.token,
                session_id=state.session_id,
            )
    finally:
        state.token = None
        state.session_id = None
        state.messages.clear()
        ui.navigate.to("/login")

