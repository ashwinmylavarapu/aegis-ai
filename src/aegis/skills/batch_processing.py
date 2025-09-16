from typing import List, Dict
from loguru import logger

async def process_posts_in_batches(orchestrator, post_selectors: List[str]) -> List[Dict[str, str]]:
    """
    Takes a list of post selectors, iterates through them in a fast loop,
    and returns a list of all extracted post details. This is a high-performance
    tool that avoids calling the LLM repeatedly inside a loop.
    """
    logger.info(f"Starting batch processing for {len(post_selectors)} posts.")
    all_post_details = []
    
    for i, selector in enumerate(post_selectors):
        # Adding a small log to show progress without being overwhelming
        if (i + 1) % 5 == 0 or (i + 1) == len(post_selectors):
            logger.info(f"Processing post {i + 1}/{len(post_selectors)}...")
            
        details = await orchestrator.browser_adapter.get_post_details(post_selector=selector)
        
        # Only add posts where details could be successfully extracted
        if details and details.get("author") != "Error":
            all_post_details.append(details)
            
    logger.success(f"Successfully processed and extracted details from {len(all_post_details)} posts in a single batch.")
    return all_post_details