"""
Main chat page for Curamyn frontend.

POLISHED UI with modern design, icons, tooltips, and animations.
"""

from typing import Dict, Any, List
from nicegui import ui, app
import asyncio
from fastapi import Request
import json
from frontend.state.app_state import state
from frontend.api.upload_client import send_ai_interaction
from frontend.api.consent_client import update_consent, get_consent
from frontend.api.memory_client import delete_memory
from frontend.api.auth_client import logout_user
from frontend.api.chat_history_client import fetch_chat_history
from frontend.utils.logger import get_logger


logger = get_logger(__name__)

# =================================================
# GLOBAL STATE
# =================================================
CHAT_CONTAINER = None
UPLOAD_WIDGET = None
TYPING_INDICATOR = None
CURRENT_MODE = "text"
CURRENT_IMAGE_TYPE = None
PENDING_FILE_BYTES = None
CONSENT_MENU = None
DELETE_DIALOG = None
MODE_BADGE = None


# =================================================
# TYPING INDICATOR
# =================================================
def _create_typing_indicator():
    """Animated typing indicator."""
    with ui.row().classes(
        "w-full justify-start items-center gap-2 px-4 py-2 animate-fade-in"
    ):
        ui.avatar("C", color="bg-gradient-to-br from-emerald-500 to-teal-600").classes(
            "text-white text-sm shadow-lg"
        )

        with ui.card().classes(
            "bg-gradient-to-r from-slate-800 to-slate-700 px-4 py-3 rounded-2xl border border-emerald-500/30 shadow-lg"
        ):
            with ui.row().classes("gap-1 items-center"):
                ui.label("Curamyn is thinking").classes(
                    "text-slate-200 text-sm mr-2 font-medium"
                )

                ui.html(
                    """
                    <div class="flex gap-1">
                        <div class="w-2 h-2 bg-emerald-400 rounded-full animate-bounce shadow-sm" style="animation-delay: 0ms"></div>
                        <div class="w-2 h-2 bg-emerald-400 rounded-full animate-bounce shadow-sm" style="animation-delay: 150ms"></div>
                        <div class="w-2 h-2 bg-emerald-400 rounded-full animate-bounce shadow-sm" style="animation-delay: 300ms"></div>
                    </div>
                """,
                    sanitize=False,
                )


def _show_typing_indicator():
    global TYPING_INDICATOR
    if TYPING_INDICATOR is None:
        TYPING_INDICATOR = ui.column().classes("w-full")
        with TYPING_INDICATOR:
            _create_typing_indicator()
        ui.run_javascript(
            """
            setTimeout(() => {
                const el = document.querySelector('.chat-scroll');
                if (el) {
                    el.scrollTo({top: el.scrollHeight, behavior: 'smooth'});
                }
            }, 50);
            """
        )


def _hide_typing_indicator():
    global TYPING_INDICATOR
    if TYPING_INDICATOR:
        try:
            TYPING_INDICATOR.clear()
            TYPING_INDICATOR.delete()
        except:
            pass
        finally:
            TYPING_INDICATOR = None


# =================================================
# MAIN PAGE
# =================================================
def show_chat_page() -> None:
    global CHAT_CONTAINER, CONSENT_MENU, DELETE_DIALOG, MODE_BADGE

    logger.debug("Rendering polished chat page")
    ui.dark_mode().enable()

    # Add custom CSS for animations
    ui.add_head_html(
        """
    <style>
        @keyframes fade-in {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .animate-fade-in {
            animation: fade-in 0.3s ease-out;
        }
        
        /* Custom scrollbar */
        .chat-scroll::-webkit-scrollbar {
            width: 8px;
        }
        .chat-scroll::-webkit-scrollbar-track {
            background: #1e293b;
        }
        .chat-scroll::-webkit-scrollbar-thumb {
            background: #475569;
            border-radius: 4px;
        }
        .chat-scroll::-webkit-scrollbar-thumb:hover {
            background: #64748b;
        }
        
        /* Glassmorphism effect */
        .glass {
            background: rgba(15, 23, 42, 0.8);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
        }
    </style>
    """
    )

    # ================= IMPROVED DELETE DIALOG =================
    DELETE_DIALOG = ui.dialog()
    with DELETE_DIALOG, ui.card().classes("p-6 bg-slate-900 border border-red-500/30"):
        ui.icon("warning", size="lg", color="red-500").classes("mb-2")
        ui.label("Delete All Memory?").classes("text-xl font-bold text-white mb-2")
        ui.label(
            "This action cannot be undone. All your chat history and session data will be permanently deleted."
        ).classes("text-slate-400 text-sm mb-6")
        with ui.row().classes("gap-3 w-full justify-end"):
            ui.button(
                "Cancel",
                on_click=DELETE_DIALOG.close,
            ).props(
                "flat"
            ).classes("text-slate-300")

            ui.button(
                "Delete",
                on_click=_handle_confirm_delete,
            ).props(
                "color=red"
            ).classes("shadow-lg")

    # ================= PAGE LAYOUT =================
    with ui.column().classes(
        "h-screen w-full overflow-hidden bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950"
    ):

        # ---------- ENHANCED HEADER ----------
        with ui.row().classes(
            "w-full px-6 py-4 glass border-b border-slate-700/50 justify-between items-center shrink-0 shadow-lg"
        ):
            # Logo and title
            with ui.row().classes("items-center gap-3"):
                ui.icon("health_and_safety", size="md", color="emerald-400")
                with ui.column().classes("gap-0"):
                    ui.label("Curamyn").classes(
                        "text-2xl font-bold bg-gradient-to-r from-emerald-400 to-teal-400 bg-clip-text text-transparent"
                    )
                    ui.label("AI Health Companion").classes("text-xs text-slate-400")

            # Action buttons
            with ui.row().classes("gap-2"):
                # Consent button with icon
                consent_btn = (
                    ui.button(icon="privacy_tip")
                    .props("flat round")
                    .classes("text-slate-300 hover:text-emerald-400 transition-colors")
                    .tooltip("Manage Privacy Settings")
                )
                CONSENT_MENU = _render_consent_menu(consent_btn)

                # Delete memory button
                ui.button(icon="delete_sweep", on_click=_open_delete_dialog).props(
                    "flat round"
                ).classes(
                    "text-slate-300 hover:text-red-400 transition-colors"
                ).tooltip(
                    "Clear All Memory"
                )

                # Logout button
                ui.button(
                    icon="logout",
                    on_click=lambda: _logout(CHAT_CONTAINER),
                ).props("flat round").classes(
                    "text-slate-300 hover:text-blue-400 transition-colors"
                ).tooltip(
                    "Logout"
                )

        # ---------- CHAT AREA ----------
        with ui.element("div").classes("flex-1 w-full overflow-y-auto chat-scroll"):
            CHAT_CONTAINER = ui.column().classes(
                "w-full max-w-5xl mx-auto px-6 py-6 gap-4"
            )

        # ---------- ENHANCED INPUT BAR ----------
        _render_input_bar()

    ui.run_javascript(
        """
        setTimeout(() => {
            fetch('/_nicegui_internal/load_history', { method: 'POST' });
        }, 50);
        """
    )


# =================================================
# HISTORY LOADING
# =================================================
@app.post("/_nicegui_internal/load_history")
def load_history_ui() -> dict:
    global CHAT_CONTAINER

    if CHAT_CONTAINER is None:
        return {"ok": False}

    try:
        CHAT_CONTAINER.clear()

        with CHAT_CONTAINER:
            _add_ai("Hi 👋 How can I help you today?")

        if state.token and state.session_id:
            try:
                messages = fetch_chat_history(
                    token=state.token,
                    session_id=state.session_id,
                )

                with CHAT_CONTAINER:
                    for message in messages:
                        _render_message(message, CHAT_CONTAINER)

            except Exception:
                logger.exception("Failed to load chat history")

        return {"ok": True}

    except Exception:
        logger.exception("Failed to initialize chat UI")
        return {"ok": False}


# ... (keeping all your existing message functions: _add_user, _add_ai, add_user_audio, etc.)
# ... (keeping all your existing helper functions)

# I'll just update the key UI functions below:


# =================================================
# IMPROVED CONSENT MENU
# =================================================
def _render_consent_menu(button):
    """Enhanced consent menu with better styling."""
    with ui.menu().classes("p-4 bg-slate-900 border border-slate-700") as menu:
        with ui.column().classes("gap-4 min-w-[300px]"):
            with ui.row().classes("items-center gap-2 mb-2"):
                ui.icon("shield", color="emerald-400")
                ui.label("Privacy & Consent").classes("text-lg font-bold text-white")

            ui.separator().classes("bg-slate-700")

            ui.label("Control what data Curamyn can process:").classes(
                "text-sm text-slate-400 mb-3"
            )

            mem = ui.checkbox(
                "Remember conversations",
                value=state.consent["memory"],
            ).classes("text-white")
            ui.label("Store chat history for context").classes(
                "text-xs text-slate-500 ml-8 -mt-2"
            )

            img = ui.checkbox(
                "Process images",
                value=state.consent["image"],
            ).classes("text-white mt-2")
            ui.label("Allow X-ray and skin image analysis").classes(
                "text-xs text-slate-500 ml-8 -mt-2"
            )

            doc = ui.checkbox(
                "Process documents",
                value=state.consent["document"],
            ).classes("text-white mt-2")
            ui.label("Allow medical report uploads").classes(
                "text-xs text-slate-500 ml-8 -mt-2"
            )

            voice = ui.checkbox(
                "Process voice",
                value=state.consent.get("voice", False),
            ).classes("text-white mt-2")
            ui.label("Enable voice interactions").classes(
                "text-xs text-slate-500 ml-8 -mt-2"
            )

            def save() -> None:
                if not state.token:
                    ui.notify("You are not authenticated.", type="negative")
                    return

                new_consent = {
                    "memory": mem.value,
                    "image": img.value,
                    "document": doc.value,
                    "voice": voice.value,
                }

                try:
                    update_consent(token=state.token, consent_data=new_consent)
                    state.consent = new_consent
                    ui.notify("✓ Privacy settings updated", type="positive")
                    menu.close()
                except Exception:
                    logger.exception("Failed to update consent")
                    ui.notify("Failed to update settings", type="negative")

            ui.separator().classes("bg-slate-700 my-3")

            ui.button("Save Changes", on_click=save, icon="check").props(
                "color=emerald"
            ).classes("w-full shadow-lg")

    button.on_click(menu.open)
    return menu


# =================================================
# ENHANCED INPUT BAR
# =================================================
def _render_input_bar() -> None:
    global UPLOAD_WIDGET, MODE_BADGE

    with ui.element("div").classes(
        "w-full glass border-t border-slate-700/50 p-4 shrink-0 shadow-2xl"
    ):
        with ui.column().classes("w-full max-w-5xl mx-auto gap-3"):

            # Mode indicator badge
            MODE_BADGE = ui.label(f"Mode: {CURRENT_MODE.upper()}").classes(
                "text-xs px-3 py-1 bg-emerald-500/20 text-emerald-400 rounded-full font-medium w-fit"
            )

            with ui.row().classes("w-full items-center gap-2"):

                # Mode selection dropdown
                with ui.menu() as type_menu:
                    ui.menu_item("💬 Text", on_click=_set_text_mode)
                    ui.separator()
                    ui.menu_item(
                        "🩻 X-ray Image", on_click=lambda: _set_image_mode("xray")
                    )
                    ui.menu_item(
                        "🔬 Skin Image", on_click=lambda: _set_image_mode("skin")
                    )
                    ui.menu_item("📄 Medical Document", on_click=_set_document_mode)

                ui.button(
                    icon="add_circle",
                    on_click=type_menu.open,
                ).props("flat round").classes(
                    "text-slate-400 hover:text-emerald-400 transition-colors"
                ).tooltip(
                    "Change Input Type"
                )

                # File upload (hidden)
                UPLOAD_WIDGET = (
                    ui.upload(
                        auto_upload=True,
                        on_upload=_on_file_selected,
                    )
                    .props("accept=*/*")
                    .classes("hidden")
                )

                # Text input
                input_box = (
                    ui.input(placeholder="Type your message...")
                    .props("outlined dense dark")
                    .classes("flex-1 bg-slate-800/50 rounded-xl border-slate-700")
                    .on("keydown.enter", lambda: asyncio.create_task(_send(input_box)))
                )

                # Send button
                ui.button(
                    icon="send",
                    on_click=lambda: asyncio.create_task(_send(input_box)),
                ).props("round color=emerald").classes(
                    "shadow-lg hover:shadow-emerald-500/50 transition-all"
                ).tooltip(
                    "Send Message"
                )

                # Voice controls
                with ui.row().classes("gap-1"):
                    ui.button(
                        icon="mic",
                        on_click=_start_recording,
                    ).props("flat round").classes(
                        "text-slate-400 hover:text-red-400 transition-colors"
                    ).tooltip(
                        "Start Recording"
                    )

                    ui.button(
                        icon="stop",
                        on_click=_stop_recording,
                    ).props("flat round").classes(
                        "text-slate-400 hover:text-red-500 transition-colors"
                    ).tooltip(
                        "Stop Recording"
                    )

                # Audio player (compact)
                ui.html(
                    """
                    <audio id="ai-audio-player" controls
                           class="h-8"
                           style="width:140px; opacity:0.8;">
                    </audio>
                    """,
                    sanitize=False,
                )


# Mode update functions with badge refresh
def _set_text_mode():
    global CURRENT_MODE, CURRENT_IMAGE_TYPE, PENDING_FILE_BYTES, MODE_BADGE
    CURRENT_MODE = "text"
    CURRENT_IMAGE_TYPE = None
    PENDING_FILE_BYTES = None
    if MODE_BADGE:
        MODE_BADGE.set_text(f"Mode: TEXT")
        MODE_BADGE.classes(
            replace="text-xs px-3 py-1 bg-blue-500/20 text-blue-400 rounded-full font-medium w-fit"
        )


def _set_image_mode(img_type: str):
    global CURRENT_MODE, CURRENT_IMAGE_TYPE, MODE_BADGE
    CURRENT_MODE = "image"
    CURRENT_IMAGE_TYPE = img_type
    if MODE_BADGE:
        MODE_BADGE.set_text(f"Mode: {img_type.upper()} IMAGE")
        MODE_BADGE.classes(
            replace="text-xs px-3 py-1 bg-purple-500/20 text-purple-400 rounded-full font-medium w-fit"
        )


def _set_document_mode():
    global CURRENT_MODE, CURRENT_IMAGE_TYPE, MODE_BADGE
    CURRENT_MODE = "document"
    CURRENT_IMAGE_TYPE = "document"
    if MODE_BADGE:
        MODE_BADGE.set_text(f"Mode: DOCUMENT")
        MODE_BADGE.classes(
            replace="text-xs px-3 py-1 bg-orange-500/20 text-orange-400 rounded-full font-medium w-fit"
        )


# ... (Keep all your existing functions for _add_user, _add_ai, _send_text, _send_file, etc.)
# ... (Just copy them from your original file - they work perfectly!)

# Since the file is getting long, I'll indicate where to paste your existing functions:
# PASTE HERE: All your existing message rendering, sending, and helper functions
