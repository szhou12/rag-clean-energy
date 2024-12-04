import os
import yaml

class PromptManager:
    def __init__(self, llm_name: str, yaml_file: str = "prompts.yaml"):
        """
        Load prompts from a YAML file from a path (specific to the PromptManager's directory).

        :param llm_name: Type of LLM to use (e.g., 'gpt', 'claude').
        :param yaml_file: YAML file name containing prompts. Defaults to 'prompts.yaml'.
        """
        self.llm_type = llm_name
        self.yaml_path = os.path.join(os.path.dirname(__file__), yaml_file)
        self.prompts = self._load_prompts()

    def _load_prompts(self) -> dict:
        """Load and parse prompts from the YAML file."""
        try:
            with open(self.yaml_path, 'r') as file:
                return yaml.safe_load(file).get("prompts", {})
        except FileNotFoundError:
            raise FileNotFoundError(f"Prompt YAML file not found at {self.yaml_path}")
        except yaml.YAMLError as e:
            raise RuntimeError(f"Error parsing YAML file: {e}")

    def get_prompt(self, key: str) -> dict:
        """
        Retrieve the prompt for the specified key and LLM type.
        
        :param key: The key identifying the prompt in the YAML file (e.g., 'context_query', 'response_template').
        :return: A dictionary of prompts for the selected LLM type.
        """
        prompt = self.prompts.get(key, {})
        return prompt.get(self.llm_type, {})

    def format_prompt(self, key: str, **kwargs) -> str:
        """
        Dynamically format a prompt by filling placeholders with values.

        :param key: The key identifying the prompt in the YAML file.
        :param kwargs: Arguments to format the prompt with.
        :return: Formatted prompt string.
        """
        prompt_data = self.get_prompt(key)
        if not prompt_data:
            raise ValueError(f"Prompt for key '{key}' and LLM type '{self.llm_type}' not found.")
        
        return {k: v.format(**kwargs) if isinstance(v, str) else v for k, v in prompt_data.items()}
