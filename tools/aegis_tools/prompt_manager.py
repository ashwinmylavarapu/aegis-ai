"""
Manages the loading and assembly of prompt templates for the CLI tools.
"""
from pathlib import Path

# The project root is calculated to find the 'prompts' and 'src' directories correctly.
PROJ_ROOT = Path(__file__).resolve().parents[2]

class PromptManager:
    """
    Loads prompt templates and injects dynamic content.
    """
    def __init__(self, prompts_root: Path = PROJ_ROOT / "tools/aegis_tools/prompts"):
        if not prompts_root.is_dir():
            raise FileNotFoundError(f"Prompts root directory not found at: {prompts_root}")
        self.prompts_root = prompts_root

    def get_prompt(self, tool_name: str, context: dict) -> str:
        """
        Assembles a complete prompt for a given tool.

        Args:
            tool_name: The name of the tool (e.g., 'playbook_creator').
            context: A dictionary of placeholders and their values.

        Returns:
            The final, assembled prompt string.
        """
        prompt_dir = self.prompts_root / tool_name
        if not prompt_dir.is_dir():
            raise FileNotFoundError(f"Prompt directory not found for tool: {tool_name}")

        template_path = prompt_dir / "meta_prompt.md"
        if not template_path.exists():
            raise FileNotFoundError(f"Main prompt template '{template_path.name}' not found for tool: {tool_name}")

        template = template_path.read_text(encoding="utf-8")

        # Load and inject content from other files like schema and examples
        template = self._inject_file_content(template, prompt_dir, "schema_definition", "schema_definition.txt")
        template = self._inject_file_content(template, prompt_dir, "examples", "examples.md")

        # Inject dynamic context provided at runtime
        for key, value in context.items():
            template = template.replace(f"{{{{{key}}}}}", str(value))

        return template

    def _inject_file_content(self, template: str, base_dir: Path, placeholder: str, filename: str) -> str:
        """Helper to read a file and replace a placeholder in the template."""
        file_path = base_dir / filename
        if f"{{{{{placeholder}}}}}" in template:
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                return template.replace(f"{{{{{placeholder}}}}}", content)
            else:
                # If the file is missing, just remove the placeholder
                return template.replace(f"{{{{{placeholder}}}}}", f"[Content for '{filename}' not found]")
        return template