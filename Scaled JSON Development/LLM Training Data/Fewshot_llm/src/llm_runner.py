"""
LLM Runner - Executes few-shot prompts using Anthropic Claude API
"""
import anthropic
import json
from datetime import datetime
import os


class LLMRunner:
    """Handles LLM API calls and response management."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        """Initialize LLM runner with API key and model."""
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def run_system(self, system_key: str, system_name: str, system_prompt: str,
                   few_shot_examples: list, test_prompt: str,
                   max_tokens: int = 2000, temperature: float = 1.0, top_p: float = 0.999):
        """
        Run a single system with few-shot examples.

        Args:
            system_key: System identifier (e.g., "1", "2x2")
            system_name: Human-readable system name
            system_prompt: System instruction prompt
            few_shot_examples: List of example dicts with "input" and "output"
            test_prompt: Test prompt to generate output for
            max_tokens: Maximum tokens for response
            temperature: Sampling temperature
            top_p: Nucleus sampling parameter

        Returns:
            dict: Response data including output, tokens used, timestamp
        """
        # Build messages from few-shot examples
        messages = []
        for example in few_shot_examples:
            messages.append({
                "role": "user",
                "content": json.dumps(example["input"], indent=2)
            })
            messages.append({
                "role": "assistant",
                "content": json.dumps(example["output"], indent=2)
            })

        # Add test prompt
        messages.append({
            "role": "user",
            "content": test_prompt
        })

        # Call API
        print(f"\n{'='*80}")
        print(f"Running System {system_key}: {system_name}")
        print(f"{'='*80}\n")
        print("Calling API...")

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            system=system_prompt,
            messages=messages
        )

        # Extract response
        output_text = response.content[0].text

        print(f"\n{'='*80}")
        print("RESPONSE:")
        print(f"{'='*80}")
        print(output_text)
        print(f"\n{'='*80}")

        # Build result
        result = {
            "timestamp": datetime.now().isoformat(),
            "system_key": system_key,
            "system_name": system_name,
            "model": self.model,
            "parameters": {
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": top_p
            },
            "system_prompt": system_prompt,
            "few_shot_count": len(few_shot_examples),
            "test_prompt": test_prompt,
            "response": output_text,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            }
        }

        print(f"Tokens used - Input: {response.usage.input_tokens}, Output: {response.usage.output_tokens}")
        print(f"{'='*80}\n")

        return result

    def save_result(self, result: dict, output_dir: str = "outputs"):
        """Save result to JSON file."""
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"system_{result['system_key']}_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, 'w') as f:
            json.dump(result, f, indent=2)

        print(f"Output saved to: {filepath}\n")
        return filepath
