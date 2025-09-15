import os
from dotenv import load_dotenv
from loguru import logger
from typing import Dict, Any

# Load environment variables from a .env file at the project root
load_dotenv()

async def linkedin_login(orchestrator, **kwargs) -> str:
    """
    A custom skill to log into LinkedIn using credentials from environment variables.
    
    This skill orchestrates multiple browser actions to complete the login flow.
    It relies on LINKEDIN_EMAIL and LINKEDIN_PASSWORD being set in a .env file.
    
    Args:
        orchestrator: The main orchestrator instance, providing access to browser tools.
        **kwargs: Additional arguments (not used in this skill).
        
    Returns:
        A string summarizing the outcome of the login attempt.
    """
    logger.info("[SKILL] Starting LinkedIn login process.")
    
    email = os.getenv("LINKEDIN_EMAIL")
    password = os.getenv("LINKEDIN_PASSWORD")

    if not email or not password:
        error_msg = "Error: LINKEDIN_EMAIL or LINKEDIN_PASSWORD not found in environment variables."
        logger.error(error_msg)
        return error_msg

    try:
        # Step 1: Navigate to the LinkedIn login page
        await orchestrator.browser_adapter.navigate(url="https://www.linkedin.com/login")

        # Step 2: Find and type in the email field
        email_selector = await orchestrator.browser_adapter.find_element(query="username or email input")
        if "Error" in email_selector:
            return f"Login failed: Could not find the email field. {email_selector}"
        await orchestrator.browser_adapter.type_text(selector=email_selector, text=email)

        # Step 3: Find and type in the password field
        password_selector = await orchestrator.browser_adapter.find_element(query="password input")
        if "Error" in password_selector:
            return f"Login failed: Could not find the password field. {password_selector}"
        await orchestrator.browser_adapter.type_text(selector=password_selector, text=password)

        # Step 4: Find and click the sign-in button
        signin_selector = await orchestrator.browser_adapter.find_element(query="Sign in button")
        if "Error" in signin_selector:
            return f"Login failed: Could not find the sign-in button. {signin_selector}"
        await orchestrator.browser_adapter.click(selector=signin_selector)

        # A small delay to allow the page to load and verify login success
        await asyncio.sleep(5) 
        
        logger.success("LinkedIn login successful.")
        return "Successfully logged into LinkedIn."

    except Exception as e:
        logger.error(f"An unexpected error occurred during LinkedIn login: {e}")
        return f"An unexpected error occurred during login: {e}"