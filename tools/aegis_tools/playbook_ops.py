# (Imports remain the same)
import asyncio
from pathlib import Path
import typer
from typing_extensions import Annotated
import yaml
import re
import inspect

from tools.aegis_tools.prompt_manager import PromptManager
from src.aegis.adapters.outbound.llm_adapter_factory import get_llm_adapter
from src.aegis.adapters.outbound.native_os_adapter import NativeOSAdapter
from src.aegis.core.models import Message

app = typer.Typer()
PROJ_ROOT = Path(__file__).resolve().parents[2]

# (_get_tools_config, _get_available_skills, _extract_yaml_from_response remain the same)
def _get_tools_config() -> dict:
    config_path = PROJ_ROOT / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError("Could not find config.yaml in the project root.")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    tools_config = config.get("tools")
    if not tools_config:
        raise ValueError("A 'tools' section is missing from config.yaml.")
    return tools_config

def _get_available_skills() -> str:
    skills = []
    for name, func in inspect.getmembers(NativeOSAdapter, predicate=inspect.isfunction):
        if not name.startswith("_"):
            sig = inspect.signature(func)
            params = ", ".join([f"{p.name}: {p.annotation or 'any'}" for p in sig.parameters.values() if p.name != 'self'])
            skills.append(f"- `{name}({params})`")
    return "\n".join(sorted(skills))

def _extract_yaml_from_response(response_text: str) -> str:
    match = re.search(r"```yaml\n(.*?)```", response_text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return response_text.strip()

async def _generate_playbook_async(story: str, output_file: Path):
    """Async helper to perform the generation."""
    try:
        print("🔧 Initializing LLM and gathering context...")
        tools_config = _get_tools_config()
        # --- THIS IS THE FIX ---
        # Request an adapter instance WITHOUT function-calling tools.
        llm_adapter = get_llm_adapter(tools_config, load_tools=False)
        
        prompt_manager = PromptManager()
        skills_md = _get_available_skills()
        context = {"user_story": story, "available_skills": skills_md}
        final_prompt = prompt_manager.get_prompt("playbook_creator", context)
        
        print(f"🧠 Calling LLM ({llm_adapter.__class__.__name__}) to generate playbook...")
        message = Message(role="user", content=final_prompt)
        response_message = await llm_adapter.chat_completion([message])
        
        if not response_message.content:
            print("❌ Error: LLM returned an empty response.")
            return

        print("📄 Parsing LLM response...")
        playbook_yaml_str = _extract_yaml_from_response(response_message.content)
        
        try:
            yaml.safe_load(playbook_yaml_str)
        except yaml.YAMLError as e:
            print(f"❌ Error: LLM generated invalid YAML. Error: {e}")
            print(f"\n--- Raw LLM Output ---\n{response_message.content}\n--- End Raw LLM Output ---")
            return

        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(playbook_yaml_str, encoding="utf-8")
        
        print(f"✅ Successfully generated and saved playbook to: {output_file}")

    except (FileNotFoundError, ValueError) as e:
        print(f"❌ Error: A configuration or file is missing/invalid. {e}")
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")

@app.command("create")
def create_playbook(
    story: Annotated[str, typer.Option("--story", "-s", help="The natural language story or goal to convert into a playbook.")],
    output_file: Annotated[Path, typer.Option("--output", "-o", help="The path where the generated playbook YAML file will be saved.")]
):
    """Generates a new playbook YAML file from a natural language story."""
    asyncio.run(_generate_playbook_async(story, output_file))

@app.command("validate")
def validate_playbook(
    playbook_file: Annotated[Path, typer.Argument(help="The path to the playbook YAML file to validate.", exists=True, file_okay=True, dir_okay=False, readable=True)]
):
    """Validates the structure of a playbook YAML file against the Aegis models."""
    print(f"✅ Placeholder: Validating playbook: {playbook_file}")