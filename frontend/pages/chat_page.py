"""
Main chat page for Curamyn frontend.

Handles UI layout, chat interactions, audio recording,
file uploads, consent management, memory actions, and logout.

ENHANCED with typing indicators and loading states.
"""

from typing import Dict, Any, List
from nicegui import ui, app
import asyncio
from fastapi import Request
import json
from frontend.state.app_state import state
from frontend.api.upload_client import send_ai_interaction
from frontend.api.consent_client import update_consent
from frontend.api.memory_client import delete_memory
from frontend.api.auth_client import logout_user
from frontend.api.chat_history_client import fetch_chat_history
from frontend.utils.logger import get_logger


logger = get_logger(__name__)

# =================================================
# GLOBAL STATE (NO UI OBJECTS)
# =================================================
CHAT_CONTAINER = None
UPLOAD_WIDGET = None
TYPING_INDICATOR = None  # NEW: For typing animation

CURRENT_MODE = "text"
CURRENT_IMAGE_TYPE = None
PENDING_FILE_BYTES = None

CONSENT_MENU = None
DELETE_DIALOG = None
MODE_LABEL = None


# =================================================
# TYPING INDICATOR COMPONENT
# =================================================
def _create_typing_indicator():
    """
    Create an animated typing indicator to show AI is thinking.
    """
    with ui.row().classes("w-full justify-start items-center gap-2 px-4 py-2"):
        ui.avatar("C", color="bg-emerald-600").classes("text-white text-sm")

        with ui.card().classes(
            "bg-slate-800 px-4 py-3 rounded-2xl border border-slate-700"
        ):
            with ui.row().classes("gap-1 items-center"):
                ui.label("Curamyn is thinking").classes("text-slate-300 text-sm mr-2")

                # Animated dots
                ui.html(
                    """
                    <div class="flex gap-1">
                        <div class="w-2 h-2 bg-emerald-500 rounded-full animate-bounce" style="animation-delay: 0ms"></div>
                        <div class="w-2 h-2 bg-emerald-500 rounded-full animate-bounce" style="animation-delay: 150ms"></div>
                        <div class="w-2 h-2 bg-emerald-500 rounded-full animate-bounce" style="animation-delay: 300ms"></div>
                    </div>
                """,
                    sanitize=False,
                )


def _show_typing_indicator():
    """
    Show the typing indicator in the chat container.
    Must be called from within CHAT_CONTAINER context.
    """
    global TYPING_INDICATOR

    if TYPING_INDICATOR is None:
        TYPING_INDICATOR = ui.column().classes("w-full")
        with TYPING_INDICATOR:
            _create_typing_indicator()

        #  Scroll happens in the same context
        ui.run_javascript(
            """
            setTimeout(() => {
                const el = document.querySelector('.chat-scroll');
                if (el) {
                    el.scrollTo({
                        top: el.scrollHeight,
                        behavior: 'smooth'
                    });
                }
            }, 50);
            """
        )
        logger.debug("Typing indicator shown")


def _hide_typing_indicator():
    """
    Remove the typing indicator from the chat container.
    Must be called from within CHAT_CONTAINER context.
    """
    global TYPING_INDICATOR

    if TYPING_INDICATOR:
        try:
            TYPING_INDICATOR.clear()
            TYPING_INDICATOR.delete()
        except (ValueError, RuntimeError) as e:
            # Element already removed or not in parent's children list
            logger.debug(f"Typing indicator already removed: {e}")
        finally:
            TYPING_INDICATOR = None

        logger.debug("Typing indicator hidden")


# =================================================
# MAIN PAGE
# =================================================
def show_chat_page() -> None:
    """
    Main chat page with working mode indicator
    """
    global CHAT_CONTAINER, CONSENT_MENU, DELETE_DIALOG, MODE_LABEL

    logger.debug("Rendering chat page")

    ui.dark_mode().enable()

    # Add CSS to prevent accidental menu opening
    ui.add_head_html(
        """
    <style>
        /* Disable hover/touch activation for menu */
        .q-menu {
            pointer-events: auto !important;
        }
        
        /* Prevent accidental activation */
        .q-btn--round:hover .q-menu {
            display: none !important;
        }
    </style>
    """
    )

    # ================= DELETE MEMORY DIALOG =================
    DELETE_DIALOG = ui.dialog()
    with DELETE_DIALOG:
        ui.label("Delete memory?")
        with ui.row().classes("gap-4"):
            ui.button("Cancel", on_click=DELETE_DIALOG.close)
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
                ui.button(
                    "LOGOUT",
                    on_click=lambda: _logout(CHAT_CONTAINER),
                )

        # ---------- CHAT AREA ----------
        with ui.element("div").classes("flex-1 w-full overflow-y-auto chat-scroll"):
            CHAT_CONTAINER = ui.column().classes(
                "w-full max-w-6xl mx-auto px-6 py-6 gap-3"
            )

            logger.info(
                "UI slot active",
                extra={"chat_container_ready": True},
            )

        #  Mode indicator INSIDE the layout (before input bar)
        with ui.column().classes("w-full bg-slate-900/50 px-4 py-2 shrink-0"):
            MODE_LABEL = ui.label("📝 Current mode: TEXT").classes(
                "text-xs text-slate-400 text-center"
            )

        # ---------- INPUT BAR ----------
        _render_input_bar()

    # Browser triggers history load AFTER DOM + slot exist
    ui.run_javascript(
        """
        setTimeout(() => {
            fetch('/_nicegui_internal/load_history', { method: 'POST' });
        }, 50);
    """
    )


@app.post("/_nicegui_internal/load_history")
def load_history_ui() -> dict:
    """
    Load chat history and render it safely inside the UI slot.
    ALWAYS shows welcome message at start of session, followed by history.
    """
    global CHAT_CONTAINER

    if CHAT_CONTAINER is None:
        logger.warning("CHAT_CONTAINER not ready")
        return {"ok": False}

    try:
        CHAT_CONTAINER.clear()

        #  ALWAYS show welcome message at session start
        with CHAT_CONTAINER:
            _add_ai("Hi 👋 How can I help you today?")

        # Then load and show any existing chat history
        if state.token and state.session_id:
            try:
                messages = fetch_chat_history(
                    token=state.token,
                    session_id=state.session_id,
                )

                logger.info(
                    "Rendering chat history in UI",
                    extra={"count": len(messages)},
                )

                with CHAT_CONTAINER:
                    for message in messages:
                        _render_message(message, CHAT_CONTAINER)

            except Exception:
                logger.exception("Failed to load chat history")
                # Welcome message already shown, just log the error

        return {"ok": True}

    except Exception:
        logger.exception("Failed to initialize chat UI")
        return {"ok": False}


# =================================================
# INTERNAL ENDPOINTS
# =================================================
def _add_user(text: str) -> None:
    """
    Render a user message in the chat UI and store it.

    Args:
        text: User message text.
    """
    logger.debug("Rendering user message")
    msg = {
        "author": "You",
        "text": text,
        "sent": True,
        "type": "text",
    }

    state.messages.append(msg)

    if CHAT_CONTAINER:
        with CHAT_CONTAINER:  # Ensure slot context
            _render_message(msg, CHAT_CONTAINER)

    _store_message_js(msg)

    #  Scroll in slot context
    if CHAT_CONTAINER:
        with CHAT_CONTAINER:
            _scroll_to_bottom()


def _add_ai(text: str) -> None:
    """
    Render an AI message in the chat UI and store it.

    Args:
        text: AI-generated message text.
    """
    logger.debug("Rendering AI message")

    msg = {
        "author": "Curamyn",
        "text": text,
        "sent": False,
        "type": "text",
    }

    state.messages.append(msg)

    if CHAT_CONTAINER:
        with CHAT_CONTAINER:  #  Ensure slot context
            _render_message(msg, CHAT_CONTAINER)

    _store_message_js(msg)

    #  Scroll in slot context
    if CHAT_CONTAINER:
        with CHAT_CONTAINER:
            _scroll_to_bottom()


@app.post("/_nicegui_internal/add_user_audio")
async def add_user_audio(payload: dict) -> dict:
    """
    Add user's recorded audio message to the chat UI.
    """
    audio_bytes = payload.get("audio_bytes", [])

    if audio_bytes and CHAT_CONTAINER:
        # Convert bytes array back to bytes
        audio_data = bytes(audio_bytes)

        import base64

        encoded_audio = base64.b64encode(audio_data).decode()

        msg = {
            "author": "You",
            "sent": True,
            "type": "audio",
            "audio_data": encoded_audio,
            "mime_type": "audio/webm",
        }

        state.messages.append(msg)

        with CHAT_CONTAINER:  #  Enter context ONCE
            _render_message(msg, CHAT_CONTAINER)
            _store_message_js(msg)  # Now safe - inside context
            _scroll_to_bottom()  # Now safe - inside context

    return {"ok": True}


# =================================================
# DELETE MEMORY
# =================================================


def _open_delete_dialog() -> None:
    """
    Open the delete-memory confirmation dialog.
    """
    if DELETE_DIALOG:
        DELETE_DIALOG.open()


def _handle_confirm_delete() -> None:
    """
    Handle user confirmation for memory deletion.
    """
    if DELETE_DIALOG:
        DELETE_DIALOG.close()

    _do_delete()


def _do_delete() -> None:
    """
    Execute memory deletion asynchronously.

    This clears:
    - backend memory
    - frontend state
    - browser session storage
    """
    if not CHAT_CONTAINER:
        return

    asyncio.create_task(_delete_task(CHAT_CONTAINER))


async def _delete_task(container) -> None:
    logger.info("User initiated memory deletion")

    try:
        #  BACKEND WORK (no UI calls)
        await asyncio.to_thread(delete_memory)

        state.messages.clear()
        state.session_id = None

        #  UI WORK — MUST be inside slot
        with container:
            container.clear()
            _clear_browser_chat(container)
            _add_ai("🧹 Memory cleared. How can I help you now?")
            ui.notify(
                "Memory deleted successfully",
                type="positive",
            )

        logger.info("Memory deleted successfully")

    except Exception:
        logger.exception("Memory deletion failed")

        with container:
            ui.notify(
                "Failed to delete memory. Please try again.",
                type="negative",
            )


# =================================================
# CONSENT MENU
# =================================================
def _render_consent_menu():
    """
    Render the consent preferences menu.

    Allows the user to enable or disable permissions for:
    - memory
    - images
    - documents
    - voice
    """
    with ui.menu() as menu:
        ui.label("Consent Preferences").classes("font-semibold")

        mem = ui.checkbox(
            "Allow memory",
            value=state.consent["memory"],
        )
        img = ui.checkbox(
            "Allow images",
            value=state.consent["image"],
        )
        doc = ui.checkbox(
            "Allow documents",
            value=state.consent["document"],
        )
        voice = ui.checkbox(
            "Allow voice",
            value=state.consent.get("voice", False),
        )

        def save() -> None:
            """
            Save updated consent preferences to backend.
            """
            if not state.token:
                ui.notify(
                    "You are not authenticated.",
                    type="negative",
                )
                return

            new_consent = {
                "memory": mem.value,
                "image": img.value,
                "document": doc.value,
                "voice": voice.value,
            }

            logger.info(
                "Updating user consent",
                extra={"consent": new_consent},
            )

            try:
                update_consent(
                    token=state.token,
                    consent_data=new_consent,
                )

                state.consent = new_consent
                ui.notify(
                    "Consent updated",
                    type="positive",
                )
                menu.close()

            except Exception:
                logger.exception("Failed to update user consent")
                ui.notify(
                    "Failed to update consent. Please try again.",
                    type="negative",
                )

        ui.button(
            "SAVE",
            on_click=save,
        )

    btn = ui.button("CONSENT")
    btn.on_click(menu.open)
    return menu


# =================================================
# INPUT BAR
# =================================================
def _render_input_bar() -> None:
    """
    Input bar with explicit button - prevents accidental menu opening
    """
    global UPLOAD_WIDGET

    logger.debug("Rendering chat input bar with fixed UI")

    with ui.element("div").classes(
        "w-full bg-[#0b1220] border-t border-gray-800 p-4 shrink-0"
    ):
        with ui.row().classes("w-full px-4 items-center gap-2"):

            # ---------- INPUT TYPE MENU (EXPLICIT BUTTON) ----------
            with ui.menu() as type_menu:
                ui.menu_item("💬 Text", on_click=_set_text_mode)
                ui.separator()
                ui.menu_item("🩻 X-ray Image", on_click=lambda: _set_image_mode("xray"))
                ui.menu_item("🔬 Skin Image", on_click=lambda: _set_image_mode("skin"))
                ui.menu_item("📄 Medical Document", on_click=_set_document_mode)

            #  Use icon button with explicit click handler - prevents touch/hover activation
            ui.button(
                icon="add_circle",
                on_click=type_menu.open,  # Only opens on explicit click
            ).props(
                "flat round"  # No hover effects
            ).classes(
                "text-slate-400 hover:text-emerald-400"
            ).tooltip(
                "Change Input Type (Click)"
            )

            # ---------- FILE UPLOAD (HIDDEN) ----------
            UPLOAD_WIDGET = (
                ui.upload(
                    auto_upload=True,
                    on_upload=_on_file_selected,
                )
                .props("accept=*/*")
                .classes("hidden")
            )

            # ---------- TEXT INPUT ----------
            input_box = (
                ui.input(placeholder="Type your message...")
                .props("outlined dense dark")
                .classes("flex-1 bg-slate-800/50 rounded-xl border-slate-700")
            )

            #  Enter key handler
            input_box.on(
                "keydown.enter", lambda e: asyncio.create_task(_send(input_box))
            )

            # ---------- SEND BUTTON ----------
            ui.button(
                icon="send",
                on_click=lambda: asyncio.create_task(_send(input_box)),
            ).props("round color=emerald").classes(
                "shadow-lg hover:shadow-emerald-500/50"
            ).tooltip(
                "Send Message"
            )

            # ---------- VOICE CONTROLS ----------
            with ui.row().classes("gap-1"):
                ui.button(
                    icon="mic",
                    on_click=_start_recording,
                ).props(
                    "flat round"
                ).classes("text-slate-400 hover:text-red-400").tooltip(
                    "Start Recording"
                )

                ui.button(
                    icon="stop",
                    on_click=_stop_recording,
                ).props(
                    "flat round"
                ).classes("text-slate-400 hover:text-red-500").tooltip("Stop Recording")


def _start_recording() -> None:
    """
    Start audio recording using the browser MediaRecorder API.

    This function:
    - Requests microphone permission
    - Initializes MediaRecorder
    - Buffers audio chunks in the browser
    """
    logger.info("User started audio recording")

    ui.notify("🎙️ Recording...", type="warning")

    ui.run_javascript(
        """
        // Unlock audio playback using user gesture (required by browsers)
        if (!window._unlockedAudio) {
            window._unlockedAudio = new Audio();
            window._unlockedAudio.muted = true;
            window._unlockedAudio.play().catch(() => {});
        }

        window._audioChunks = [];

        navigator.mediaDevices.getUserMedia({ audio: true })
            .then(stream => {
                window._mediaRecorder = new MediaRecorder(stream);
                window._mediaRecorder.ondataavailable = e => {
                    if (e.data.size > 0) {
                        window._audioChunks.push(e.data);
                    }
                };
                window._mediaRecorder.start();
            })
            .catch(err => {
                console.error('Microphone access denied', err);
                fetch('/_nicegui_internal/notify_error', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        message: 'Microphone access denied.'
                    })
                });
            });
        """
    )


async def _stop_recording() -> None:
    """
    Stop audio recording and send the captured audio
    to the backend for processing.
    """
    logger.info("User stopped audio recording")
    ui.notify("Recording stopped", type="info")

    ui.run_javascript(
        """
        if (!window._mediaRecorder) return;

        window._mediaRecorder.stop();

        window._mediaRecorder.onstop = async () => {
            const blob = new Blob(
                window._audioChunks,
                { type: 'audio/webm' }
            );

            const arrayBuffer = await blob.arrayBuffer();
            const bytes = Array.from(new Uint8Array(arrayBuffer));

            // Create audio URL for displaying user's recorded message
            const audioUrl = URL.createObjectURL(blob);
            
            // Add user's audio message to chat
            await fetch('/_nicegui_internal/add_user_audio', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    audio_url: audioUrl,
                    audio_bytes: bytes
                })
            });

            const res = await fetch('/_nicegui_api/send_voice', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(bytes),
            });

            const data = await res.json();
            //  Persist session_id in browser
            if (data.session_id) {
                sessionStorage.setItem('session_id', data.session_id);
            }
                
        };
        """
    )


@app.post("/_nicegui_api/send_voice")
async def send_voice(audio_array: list[int]) -> dict:
    """
    Receive recorded audio from the browser and send it to the AI backend.

    Args:
        audio_array: List of audio byte values from the browser.

    Returns:
        Backend AI response payload.
    """
    logger.info("Received voice input from browser")

    if not state.token:
        return {"error": "Not authenticated"}

    audio_bytes = bytes(audio_array)

    if CHAT_CONTAINER:
        with CHAT_CONTAINER:
            _show_typing_indicator()

    try:
        result = await asyncio.to_thread(
            send_ai_interaction,
            token=state.token,
            session_id=state.session_id,
            input_type="audio",
            response_mode="voice",
            audio_bytes=audio_bytes,
        )

        if CHAT_CONTAINER:
            with CHAT_CONTAINER:
                _hide_typing_indicator()

                #  Always show AI text
                if result.get("message"):
                    _add_ai(result["message"])

                if result.get("audio_base64"):
                    audio_msg = {
                        "author": "Curamyn",
                        "sent": False,
                        "type": "audio",
                        "audio_data": result["audio_base64"],
                        "mime_type": "audio/wav",
                    }
                    _render_message(audio_msg, CHAT_CONTAINER)
                    _scroll_to_bottom()

                    #  AUTO-PLAY THE LAST CHAT AUDIO
                    ui.run_javascript(
                        """
                    setTimeout(() => {
                        const audios = document.querySelectorAll('audio');
                        if (!audios.length) return;

                        const last = audios[audios.length - 1];
                        last.load();
                        last.play().catch(() => {});
                    }, 300);
                    """
                    )

        return result

    except Exception:
        logger.exception("Voice interaction failed")

        if CHAT_CONTAINER:
            with CHAT_CONTAINER:
                _hide_typing_indicator()
                ui.notify("Voice playback failed", type="negative")

        return {"error": "Voice playback failed"}


# =================================================
# MODE
# =================================================


def _set_text_mode() -> None:
    """Switch to text mode and update label."""
    global CURRENT_MODE, CURRENT_IMAGE_TYPE, PENDING_FILE_BYTES, MODE_LABEL

    CURRENT_MODE = "text"
    CURRENT_IMAGE_TYPE = None
    PENDING_FILE_BYTES = None

    # Update the label
    if MODE_LABEL:
        MODE_LABEL.set_text("📝 Current mode: TEXT")

    ui.notify("✓ Text mode", type="info", position="top", timeout=1000)
    logger.debug("Switched to TEXT mode")


def _set_image_mode(img_type: str) -> None:
    """CORRECTED: Switch to image mode and update label."""
    global CURRENT_MODE, CURRENT_IMAGE_TYPE, MODE_LABEL

    CURRENT_MODE = "image"
    CURRENT_IMAGE_TYPE = img_type

    #  Update the label
    if MODE_LABEL:
        MODE_LABEL.set_text(f"🖼️ Current mode: {img_type.upper()} IMAGE")

    ui.notify(
        f"✓ {img_type.upper()} image mode - upload your image",
        type="info",
        position="top",
        timeout=2000,
    )
    logger.debug(f"Switched to IMAGE mode: {img_type}")


def _set_document_mode() -> None:
    """Switch to document mode and update label."""
    global CURRENT_MODE, CURRENT_IMAGE_TYPE, MODE_LABEL

    CURRENT_MODE = "document"
    CURRENT_IMAGE_TYPE = "document"

    #  Update the label
    if MODE_LABEL:
        MODE_LABEL.set_text("📄 Current mode: DOCUMENT")

    ui.notify(
        "✓ Document mode - upload your report",
        type="info",
        position="top",
        timeout=2000,
    )
    logger.debug("Switched to DOCUMENT mode")


# =================================================
# FILE UPLOAD
# =================================================
async def _on_file_selected(event) -> None:
    """
    Handle file selection from the upload widget.

    Reads the file, renders a preview in the chat UI,
    and stores it as a pending message.
    """
    global PENDING_FILE_BYTES

    logger.info(
        "User selected a file",
        extra={"uploaded_filename": event.file.name},
    )

    try:
        PENDING_FILE_BYTES = await event.file.read()

        import base64
        import mimetypes

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

        if CHAT_CONTAINER:
            with CHAT_CONTAINER:
                with ui.row().classes("w-full justify-end"):
                    ui.image(data_url).classes(
                        "max-w-xs rounded-lg " "border border-gray-600"
                    )

        _store_message_js(msg)
        _scroll_to_bottom()

    except Exception:
        logger.exception("Failed to handle file upload")
        ui.notify(
            "Failed to load selected file",
            type="negative",
        )
        PENDING_FILE_BYTES = None


# =================================================
# SEND
# =================================================
async def _send(input_box) -> None:
    """Send message and auto-reset mode."""
    global PENDING_FILE_BYTES, CURRENT_MODE, CURRENT_IMAGE_TYPE, MODE_LABEL

    logger.debug(f"Sending message in {CURRENT_MODE} mode")

    if CURRENT_MODE == "text":
        text = input_box.value.strip()

        if not text:
            logger.debug("Empty text input ignored")
            return

        input_box.value = ""
        _add_user(text)

        try:
            await _send_text(text)
        except Exception:
            logger.exception("Failed to send text message")
            ui.notify("Failed to send message", type="negative")

        return

    # ---------- FILE MODE ----------
    if not PENDING_FILE_BYTES:
        ui.notify("Select a file first", type="warning")
        return

    try:
        await _send_file()

        #  Auto-reset to TEXT mode
        CURRENT_MODE = "text"
        CURRENT_IMAGE_TYPE = None
        PENDING_FILE_BYTES = None

        #  Update label
        if MODE_LABEL:
            MODE_LABEL.set_text("📝 Current mode: TEXT")

        logger.info("Auto-reset to TEXT mode after file upload")

    except Exception:
        logger.exception("Failed to send file")
        ui.notify("Failed to send file", type="negative")


def _handle_ai_response(response: dict) -> None:
    """
    Handle AI backend response.

    Responsibilities:
    - Persist a newly generated session_id
    - Keep frontend session state stable across refresh
    """
    new_session_id = response.get("session_id")

    if not new_session_id:
        logger.debug("No session_id found in AI response")
        return

    # Avoid overwriting an existing session
    if state.session_id == new_session_id:
        return

    state.session_id = new_session_id
    app.storage.user["session_id"] = new_session_id

    logger.info(
        "Session ID persisted in frontend storage",
        extra={"session_id": new_session_id},
    )


async def _send_text(text: str) -> None:
    """
    Send a text message to the AI backend and render the response.

    Args:
        text: User input text.
    """
    logger.info("Sending text message")

    if not state.token:
        logger.warning("Attempted to send text without authentication")
        ui.notify("You are not authenticated", type="negative")
        return

    # Show typing indicator
    if CHAT_CONTAINER:
        with CHAT_CONTAINER:
            _show_typing_indicator()

    try:
        response = await asyncio.to_thread(
            send_ai_interaction,
            token=state.token,
            session_id=state.session_id,
            input_type="text",
            text=text,
            response_mode="text",
        )

        # Hide typing indicator before showing response
        if CHAT_CONTAINER:
            with CHAT_CONTAINER:
                _hide_typing_indicator()

        if CHAT_CONTAINER:
            with CHAT_CONTAINER:
                _handle_ai_response(response)

        state.session_id = response.get(
            "session_id",
            state.session_id,
        )

        if state.session_id:
            ui.run_javascript(
                f"""
                sessionStorage.setItem('session_id', '{state.session_id}');
                """
            )

        message = response.get("message")
        if message:
            if CHAT_CONTAINER:
                with CHAT_CONTAINER:
                    _add_ai(message)

    except Exception:
        if CHAT_CONTAINER:
            with CHAT_CONTAINER:
                _hide_typing_indicator()

        logger.exception("Failed to send text message")
        ui.notify(
            "Failed to send message. Please try again.",
            type="negative",
        )


async def _send_file() -> None:
    """
    Send an image or document file to the AI backend
    and render the response.
    """
    global PENDING_FILE_BYTES

    logger.info(
        "Sending file to backend",
        extra={"image_type": CURRENT_IMAGE_TYPE},
    )

    if not state.token:
        logger.warning("Attempted to send file without authentication")
        ui.notify("You are not authenticated", type="negative")
        return

    # CHECK CONSENT BEFORE SENDING
    if CURRENT_IMAGE_TYPE == "document":
        if not state.consent.get("document", False):
            ui.notify(
                "Document processing is disabled. Enable it in consent settings.",
                type="warning",
            )
            PENDING_FILE_BYTES = None
            if UPLOAD_WIDGET:
                UPLOAD_WIDGET.reset()
            return
    else:
        # For images (xray, skin)
        if not state.consent.get("image", False):
            ui.notify(
                "Image processing is disabled. Enable it in consent settings.",
                type="warning",
            )
            PENDING_FILE_BYTES = None
            if UPLOAD_WIDGET:
                UPLOAD_WIDGET.reset()
            return

    # Show typing indicator
    if CHAT_CONTAINER:
        with CHAT_CONTAINER:
            _show_typing_indicator()

    try:
        response = await asyncio.to_thread(
            send_ai_interaction,
            token=state.token,
            input_type="image",
            session_id=state.session_id,
            image_type=CURRENT_IMAGE_TYPE,
            file_bytes=PENDING_FILE_BYTES,
        )

        # Hide typing indicator before showing response
        if CHAT_CONTAINER:
            with CHAT_CONTAINER:
                _hide_typing_indicator()

        #  Check for consent errors from backend (backup check)
        if response.get("message"):
            msg_lower = response.get("message", "").lower()
            if "consent" in msg_lower or "disabled" in msg_lower:
                ui.notify(response.get("message"), type="warning")
                return

        # Handle AI response
        if CHAT_CONTAINER:
            with CHAT_CONTAINER:
                _handle_ai_response(response)

        state.session_id = response.get(
            "session_id",
            state.session_id,
        )

        if state.session_id:
            ui.run_javascript(
                f"""
                sessionStorage.setItem('session_id', '{state.session_id}');
                """
            )

        text = response.get("response_text") or response.get("message")
        disclaimer = response.get("disclaimer")

        if text:
            if CHAT_CONTAINER:
                with CHAT_CONTAINER:
                    _add_ai(text)
        if disclaimer:
            if CHAT_CONTAINER:
                with CHAT_CONTAINER:
                    _add_ai(f"⚠️ {disclaimer}")

    except Exception as e:
        #  Safe cleanup on error
        if CHAT_CONTAINER:
            with CHAT_CONTAINER:
                _hide_typing_indicator()

        logger.exception("Failed to send file")

        # Check if it's a consent-related error
        error_msg = str(e)
        if "consent" in error_msg.lower() or "disabled" in error_msg.lower():
            ui.notify(
                "Image/document processing is disabled. Enable it in consent settings.",
                type="warning",
            )
        else:
            ui.notify(
                "Failed to send file. Please try again.",
                type="negative",
            )

    finally:
        PENDING_FILE_BYTES = None
        if UPLOAD_WIDGET:
            UPLOAD_WIDGET.reset()


# =================================================
# CHAT UI + BROWSER SESSION STORAGE
# =================================================


def _render_message(message: dict, container) -> None:
    """
    Render a single chat message with proper alignment based on sender type.
    Ensures user messages appear on the right and assistant messages on the left.
    """

    with container:
        msg_type = message.get("type", "text")
        is_user = message.get("sent", False)

        # ================= AUDIO =================
        if msg_type == "audio":
            data_url = (
                f"data:{message.get('mime_type')};base64,"
                f"{message.get('audio_data')}"
            )
            audio_id = f"audio-{message.get('timestamp', '')}"
            with ui.row().classes(
                "w-full justify-end" if is_user else "w-full justify-start"
            ):
                ui.html(
                    f"""
                    <audio id="{audio_id}" controls preload="auto">
                    <source src="{data_url}" type="{message.get('mime_type')}">
                    </audio>

                    """,
                    sanitize=False,
                )
                ui.run_javascript(
                    """
                  setTimeout(() => {
                  document.querySelectorAll('audio').forEach(a => a.load());
                   }, 50);
                 """
                )

            return

        # ================= IMAGE =================
        if msg_type == "image":
            data_url = (
                f"data:{message.get('mime_type')};base64,"
                f"{message.get('image_data')}"
            )

            # Image stays on RIGHT for user, LEFT for assistant
            with ui.row().classes(
                "w-full justify-end" if is_user else "w-full justify-start"
            ):
                ui.image(data_url).classes("max-w-xs rounded-lg")
            return

        # ================= TEXT =================

        with ui.row().classes(
            "w-full justify-end" if is_user else "w-full justify-start"
        ):
            ui.chat_message(
                text=message.get("text", ""),
                name=message.get("author", ""),
                sent=is_user,
            )


def _store_message_js(msg: dict) -> None:
    """
    Persist a chat message in browser sessionStorage.
    SAFE: silently skip if not in UI context.
    """
    try:
        ui.run_javascript(
            f"""
            (function() {{
                try {{
                    const existing = JSON.parse(
                        sessionStorage.getItem('chat_messages') || '[]'
                    );
                    existing.push({json.dumps(msg)});
                    sessionStorage.setItem(
                        'chat_messages',
                        JSON.stringify(existing)
                    );
                    window.chatMessages = existing;
                }} catch (err) {{
                    console.error('Failed to store chat message', err);
                }}
            }})();
            """
        )
    except RuntimeError:
        #  FastAPI endpoint or background task
        # Safe to ignore – UI thread will handle it later
        logger.debug("Skipping ui.run_javascript (no UI context)")


def _clear_browser_chat(container) -> None:
    """
    Clear all stored chat messages from browser sessionStorage.
    """

    logger.info("Clearing browser chat history")

    with container:
        ui.run_javascript(
            """
            try {
                sessionStorage.removeItem('chat_messages');
            } catch (err) {
                console.error('Failed to clear chat history', err);
            }
            """
        )


# =================================================
# SCROLL
# =================================================


def _scroll_to_bottom() -> None:
    """
    Smoothly scroll the chat container to the bottom.
    """
    ui.run_javascript(
        """
        setTimeout(() => {
            const el = document.querySelector('.chat-scroll');
            if (el) {
                el.scrollTo({
                    top: el.scrollHeight,
                    behavior: 'smooth'
                });
            }
        }, 50);
        """
    )


# =================================================
# LOGOUT
# =================================================


def _logout(container) -> None:
    """
    Logout the current user safely.

    Backend responsibilities:
    - Generate & store session summary
    - Delete session memory

    Frontend responsibilities:
    - Call backend logout with session_id
    - Clear UI + browser state
    """

    logger.info(
        "Calling backend logout",
        extra={"session_id": state.session_id},
    )

    logout_user(
        token=state.token,
        session_id=state.session_id,
    )

    _clear_browser_chat(container)

    state.token = None
    state.session_id = None
    state.messages.clear()
    ui.run_javascript("localStorage.removeItem('access_token')")

    ui.navigate.to("/login")
