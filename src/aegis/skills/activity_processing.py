from typing import List, Dict
from loguru import logger

async def process_activity_posts_in_batches(orchestrator, post_selectors: List[str]) -> List[Dict[str, str]]:
    """
    Takes a list of post selectors from an activity page, iterates through them,
    and returns a list of all post details using a specialized tool.
    """
    logger.info(f"Starting batch processing for {len(post_selectors)} activity posts.")
    all_post_details = []
    
    for i, selector in enumerate(post_selectors):
        if (i + 1) % 5 == 0 or (i + 1) == len(post_selectors):
            logger.info(f"Processing activity post {i + 1}/{len(post_selectors)}...")
            
        # Call the new, specialized browser tool
        details = await orchestrator.browser_adapter.get_activity_post_details(post_selector=selector)
        
        if details and details.get("author") != "Error":
            all_post_details.append(details)
            
    logger.success(f"Successfully processed details from {len(all_post_details)} activity posts.")
    return all_post_details