# src/aegis/adapters/outbound/omni_parser_adapter.py
import asyncio
import json
import os
import subprocess
from typing import Any, Dict, List

from loguru import logger

from aegis.adapters.outbound.base import OutboundAdapter

# Pre-set environment variables for M1 compatibility
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


class OmniParserAdapter(OutboundAdapter):
    """
    An adapter to run the OmniParser script as a subprocess and parse its output.
    """

    def __init__(self, config: Dict[str, Any]):
        self.script_path = config.get("script_path")
        self.workdir = config.get("workdir")
        if not self.script_path or not os.path.exists(self.script_path):
            raise FileNotFoundError(
                f"OmniParser script not found at path: {self.script_path}"
            )
        logger.info(
            f"OmniParserAdapter initialized with script_path: {self.script_path} and workdir: {self.workdir}"
        )

    async def see_the_page(self, screenshot_path: str) -> List[Dict[str, Any]]:
        """
        Executes the OmniParser script on a given screenshot and returns the
        structured data of visible UI elements.
        """
        if not os.path.exists(screenshot_path):
            logger.error(f"Screenshot file not found: {screenshot_path}")
            return []

        # Ensure paths are absolute to avoid ambiguity
        screenshot_path = os.path.abspath(screenshot_path)
        script_path = os.path.abspath(self.script_path)
        workdir_path = os.path.abspath(self.workdir)
        
        # --- THIS IS THE FIX ---
        # Explicitly define the output directory and ensure it exists.
        output_dir = os.path.join(workdir_path, "outputs")
        os.makedirs(output_dir, exist_ok=True)

        # Pass the explicit output directory to the script.
        command = [
            "python",
            script_path,
            "--png",
            screenshot_path,
            "--workdir",
            workdir_path,
            "--outputs",
            output_dir,
            "--enable_ocr",
        ]

        logger.info(f"Executing OmniParser command: {' '.join(command)}")

        try:
            # Run the subprocess from the project's root directory
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
            
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=project_root,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                logger.error(f"OmniParser script failed with return code {process.returncode}")
                logger.error(f"Stderr: {stderr.decode().strip()}")
                return []

            logger.info(f"OmniParser script executed successfully.")
            logger.debug(f"Stdout: {stdout.decode().strip()}")
            
            # This path will now be correct because we passed it to the script.
            results_path = os.path.join(output_dir, "results.json")
            if not os.path.exists(results_path):
                logger.error(f"OmniParser output file not found: {results_path}")
                return []

            with open(results_path, "r") as f:
                results_data = json.load(f)

            detections = results_data.get("detections", [])

            for i, element in enumerate(detections):
                element["element_id"] = f"element_{i+1}"

            return detections

        except Exception as e:
            logger.error(f"An exception occurred while running OmniParser: {e}")
            return []