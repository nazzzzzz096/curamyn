from nicegui import ui

from frontend.pages.login_page import show_login_page
from frontend.pages.signup_page import show_signup_page
from frontend.pages.onboarding_page import show_onboarding_page
from frontend.pages.chat_page import show_chat_page 
import os

@ui.page("/")
def root():
    ui.dark_mode().enable()
    ui.navigate.to("/login")   # ✅ FIXED


@ui.page("/login")
def login():
    ui.dark_mode().enable()
    show_login_page()


@ui.page("/signup")
def signup():
    ui.dark_mode().enable()
    show_signup_page()


@ui.page("/onboarding")
def onboarding():
    ui.dark_mode().enable()
    show_onboarding_page()

@ui.page("/chat")  
def chat():
    show_chat_page()

def start_app():
    ui.run(
        title="Curamyn",
        reload=False, 
         storage_secret=os.getenv("STORAGE_SECRET", "dev-secret"),  # Windows saf
    )


if __name__ == "__main__":
    start_app()
