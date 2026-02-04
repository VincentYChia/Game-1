"""
Together.ai Fine-Tuning Script for Crafting VLM/LLM Models

This script prepares and launches fine-tuning jobs on Together.ai for:
- VLM (Vision-Language Models): Smithing & Adornment (images + recipes)
- LLM (Language Models): Refining, Alchemy, Engineering (text only)

Prerequisites:
    pip install together

Setup:
    export TOGETHER_API_KEY="your-api-key"

Usage:
    # Prepare data only (convert to JSONL)
    python together_finetune.py --prepare-only --input ./training_data/smithing_custom_data.json

    # Launch fine-tuning job
    python together_finetune.py --input ./training_data/smithing_custom_data.json --model meta-llama/Llama-3.2-11B-Vision-Instruct

    # Use config file for all parameters
    python together_finetune.py --config finetune_config.json

Documentation:
    - Together.ai Fine-tuning: https://docs.together.ai/docs/fine-tuning-overview
    - Together.ai Vision: https://docs.together.ai/docs/vision-overview
    - Together Cookbook: https://github.com/togethercomputer/together-cookbook

Author: Claude
Created: 2026-02-04
"""

import json
import os
import sys
import argparse
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class FinetuneConfig:
    """
    Configuration for Together.ai fine-tuning jobs.

    All parameters can be overridden via command line or config file.
    """

    # === Model Selection ===
    # VLM Models (vision + text):
    #   - meta-llama/Llama-3.2-11B-Vision-Instruct
    #   - meta-llama/Llama-3.2-90B-Vision-Instruct
    #   - meta-llama/Llama-4-Scout-17B-16E-Instruct
    #   - Qwen/Qwen2.5-VL-72B-Instruct
    #
    # LLM Models (text only):
    #   - meta-llama/Meta-Llama-3.1-8B-Instruct
    #   - meta-llama/Meta-Llama-3.1-70B-Instruct
    #   - meta-llama/Llama-3.2-3B-Instruct
    #   - mistralai/Mixtral-8x7B-Instruct-v0.1
    model: str = "meta-llama/Llama-3.2-11B-Vision-Instruct"

    # === Training Parameters ===
    n_epochs: int = 3                    # Number of training epochs
    learning_rate: float = 1e-5          # Learning rate (1e-5 to 5e-5 typical)
    batch_size: int = 4                  # Batch size (depends on model size)
    warmup_ratio: float = 0.1            # Warmup steps as ratio of total
    n_checkpoints: int = 1               # Number of checkpoints to save

    # === LoRA Parameters ===
    lora: bool = True                    # Use LoRA (recommended for large models)
    lora_r: int = 16                     # LoRA rank (8, 16, 32, 64)
    lora_alpha: int = 32                 # LoRA alpha (typically 2x rank)
    lora_dropout: float = 0.05           # LoRA dropout

    # === Data Parameters ===
    train_on_inputs: str = "auto"        # Train on inputs: "auto", True, False
    max_seq_length: int = 4096           # Maximum sequence length

    # === Job Configuration ===
    suffix: str = "crafting-v1"          # Model suffix for identification
    wandb_project: Optional[str] = None  # W&B project for logging (optional)

    # === Discipline-specific prompts ===
    # These define the system prompts for each discipline
    system_prompts: Dict[str, str] = field(default_factory=lambda: {
        "smithing": """You are an expert item generator for a crafting RPG game. Given an image of a crafting grid and material information, generate a valid item definition.

The crafting grid shows materials arranged in specific patterns. Each material has properties like tier, category, and tags that influence the output item.

Generate items that:
- Have appropriate stats based on material tiers
- Include relevant tags from the input materials
- Follow the game's naming conventions
- Have balanced properties for gameplay""",

        "adornment": """You are an expert enchantment generator for a crafting RPG game. Given an image of an enchanting pattern and material information, generate a valid enchantment definition.

The enchanting pattern shows materials connected by vertices and edges. The geometric arrangement and materials used determine the enchantment's properties.

Generate enchantments that:
- Have effects matching the material types used
- Scale appropriately with material tiers
- Include relevant elemental or magical properties
- Follow the game's enchantment naming conventions""",

        "refining": """You are an expert material refiner for a crafting RPG game. Given a refining recipe with core and surrounding materials, determine the output refined material.

Consider:
- The core material determines the base output
- Surrounding materials modify properties like quality, elemental affinity, or special traits
- Higher tier materials produce higher tier outputs
- Material tags influence the final product's properties""",

        "alchemy": """You are an expert alchemist for a crafting RPG game. Given a recipe with ingredients in specific slots, determine the potion or consumable output.

Consider:
- Ingredient order and slot positions matter
- Material properties combine to create effects
- Tier determines potency
- Tags indicate elemental or magical properties""",

        "engineering": """You are an expert engineer for a crafting RPG game. Given a schematic with materials in different slot types, determine the device or contraption output.

Slot types include:
- FRAME: Structural base material
- CORE: Central functional component
- MODIFIER: Adjusts properties
- CATALYST: Triggers special effects

Consider material tiers and tags when determining output capabilities."""
    })


# ============================================================================
# DATA CONVERSION
# ============================================================================

class DataConverter:
    """
    Converts training data JSON to Together.ai JSONL format.

    VLM format (with images):
    {"messages": [
        {"role": "system", "content": "..."},
        {"role": "user", "content": [
            {"type": "text", "text": "..."},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
        ]},
        {"role": "assistant", "content": "..."}
    ]}

    LLM format (text only):
    {"messages": [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."}
    ]}
    """

    def __init__(self, config: FinetuneConfig):
        self.config = config

    def detect_discipline(self, data: Dict) -> str:
        """Detect discipline from training data metadata."""
        metadata = data.get('metadata', {})
        discipline = metadata.get('discipline', '')

        if discipline:
            return discipline

        # Try to infer from data structure
        if data.get('training_data'):
            sample = data['training_data'][0]
            recipe = sample.get('recipe', {})
            station_type = recipe.get('stationType', '')

            if station_type == 'smithing':
                return 'smithing'
            elif station_type == 'enchanting':
                return 'adornment'
            elif station_type == 'refining':
                return 'refining'
            elif station_type == 'alchemy':
                return 'alchemy'
            elif station_type == 'engineering':
                return 'engineering'

        return 'unknown'

    def is_vlm_discipline(self, discipline: str) -> bool:
        """Check if discipline requires vision (VLM)."""
        return discipline in ['smithing', 'adornment']

    def format_recipe_for_prompt(self, recipe: Dict) -> str:
        """Format recipe data as a readable prompt."""
        lines = []

        # Recipe ID
        lines.append(f"Recipe: {recipe.get('recipeId', 'unknown')}")
        lines.append(f"Station: {recipe.get('stationType', 'unknown')} (Tier {recipe.get('stationTier', 1)})")

        # Grid size for smithing
        if 'gridSize' in recipe:
            lines.append(f"Grid: {recipe['gridSize']}")

        # Inputs
        lines.append("\nMaterials:")

        inputs = recipe.get('inputs', [])
        if not inputs:
            # Try other input formats
            inputs = recipe.get('ingredients', [])
        if not inputs:
            inputs = recipe.get('slots', [])
        if not inputs:
            # Refining format
            core = recipe.get('coreInputs', [])
            surrounding = recipe.get('surroundingInputs', [])
            inputs = [{'type': 'core', **c} for c in core] + [{'type': 'surrounding', **s} for s in surrounding]

        for inp in inputs:
            mat_id = inp.get('materialId', 'unknown')
            qty = inp.get('quantity', 1)
            metadata = inp.get('material_metadata', {})

            mat_line = f"  - {mat_id} x{qty}"

            if metadata:
                tier = metadata.get('tier', '')
                category = metadata.get('category', '')
                tags = metadata.get('tags', [])

                details = []
                if tier:
                    details.append(f"T{tier}")
                if category:
                    details.append(category)
                if tags:
                    details.append(f"tags: {', '.join(tags[:5])}")

                if details:
                    mat_line += f" ({', '.join(details)})"

            lines.append(mat_line)

        return '\n'.join(lines)

    def generate_expected_output(self, recipe: Dict, discipline: str) -> str:
        """
        Generate the expected output for training.

        NOTE: This is a placeholder. In production, you should have actual
        output items paired with your recipes. This generates a template
        that you would replace with real item definitions.
        """
        recipe_id = recipe.get('recipeId', 'unknown')

        # Extract material info for output generation hints
        inputs = recipe.get('inputs', []) or recipe.get('ingredients', []) or recipe.get('slots', [])
        if not inputs:
            core = recipe.get('coreInputs', [])
            surrounding = recipe.get('surroundingInputs', [])
            inputs = core + surrounding

        # Determine tier from materials
        max_tier = 1
        all_tags = set()
        for inp in inputs:
            metadata = inp.get('material_metadata', {})
            tier = metadata.get('tier', 1)
            tags = metadata.get('tags', [])
            max_tier = max(max_tier, tier)
            all_tags.update(tags)

        # Generate output template based on discipline
        if discipline == 'smithing':
            output = {
                "itemId": f"output_{recipe_id}",
                "name": f"Crafted Item ({recipe_id})",
                "type": "equipment",
                "tier": max_tier,
                "tags": list(all_tags)[:10],
                "stats": {
                    "damage": max_tier * 10,
                    "durability": 100
                }
            }
        elif discipline == 'adornment':
            output = {
                "enchantmentId": f"ench_{recipe_id}",
                "name": f"Enchantment ({recipe_id})",
                "tier": max_tier,
                "tags": list(all_tags)[:10],
                "effects": [
                    {"type": "stat_bonus", "value": max_tier * 5}
                ]
            }
        elif discipline == 'refining':
            output = {
                "materialId": f"refined_{recipe_id}",
                "name": f"Refined Material ({recipe_id})",
                "tier": max_tier,
                "category": "refined",
                "tags": list(all_tags)[:10]
            }
        elif discipline == 'alchemy':
            output = {
                "potionId": f"potion_{recipe_id}",
                "name": f"Potion ({recipe_id})",
                "tier": max_tier,
                "effects": [
                    {"type": "buff", "duration": max_tier * 30}
                ],
                "tags": list(all_tags)[:10]
            }
        elif discipline == 'engineering':
            output = {
                "deviceId": f"device_{recipe_id}",
                "name": f"Device ({recipe_id})",
                "tier": max_tier,
                "power": max_tier * 20,
                "tags": list(all_tags)[:10]
            }
        else:
            output = {"id": recipe_id, "tier": max_tier}

        return json.dumps(output, indent=2)

    def convert_sample_to_message(self, sample: Dict, discipline: str) -> Dict:
        """Convert a single training sample to Together.ai message format."""
        recipe = sample.get('recipe', {})
        image_base64 = sample.get('image_base64')

        system_prompt = self.config.system_prompts.get(
            discipline,
            "You are an expert crafter. Generate appropriate output for the given recipe."
        )

        # Format the recipe as user prompt text
        recipe_text = self.format_recipe_for_prompt(recipe)
        user_prompt = f"Generate the output item for this recipe:\n\n{recipe_text}"

        # Generate expected output (assistant response)
        expected_output = self.generate_expected_output(recipe, discipline)

        messages = [
            {"role": "system", "content": system_prompt}
        ]

        # VLM format (with image)
        if self.is_vlm_discipline(discipline) and image_base64:
            user_content = [
                {"type": "text", "text": user_prompt}
            ]

            # Add image if available
            if image_base64.startswith('data:image'):
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": image_base64}
                })

            messages.append({"role": "user", "content": user_content})
        else:
            # LLM format (text only)
            messages.append({"role": "user", "content": user_prompt})

        messages.append({"role": "assistant", "content": expected_output})

        return {"messages": messages}

    def convert_file(self, input_path: str, output_path: str = None) -> str:
        """
        Convert training data JSON to JSONL format.

        Args:
            input_path: Path to input JSON file
            output_path: Path for output JSONL (default: same name with .jsonl)

        Returns:
            Path to output JSONL file
        """
        input_path = Path(input_path)

        if output_path is None:
            output_path = input_path.with_suffix('.jsonl')
        else:
            output_path = Path(output_path)

        logger.info(f"Loading training data from: {input_path}")

        with open(input_path, 'r') as f:
            data = json.load(f)

        discipline = self.detect_discipline(data)
        logger.info(f"Detected discipline: {discipline}")
        logger.info(f"VLM mode: {self.is_vlm_discipline(discipline)}")

        training_data = data.get('training_data', [])
        logger.info(f"Converting {len(training_data)} samples...")

        converted = []
        for i, sample in enumerate(training_data):
            try:
                message = self.convert_sample_to_message(sample, discipline)
                converted.append(message)
            except Exception as e:
                logger.warning(f"Failed to convert sample {i}: {e}")

        # Write JSONL
        logger.info(f"Writing JSONL to: {output_path}")
        with open(output_path, 'w') as f:
            for item in converted:
                f.write(json.dumps(item) + '\n')

        logger.info(f"Converted {len(converted)} samples successfully")

        return str(output_path)


# ============================================================================
# TOGETHER.AI CLIENT
# ============================================================================

class TogetherFineTuner:
    """
    Client for Together.ai fine-tuning operations.

    Handles:
    - File upload and validation
    - Fine-tuning job creation
    - Job monitoring
    - Model inference
    """

    def __init__(self, config: FinetuneConfig):
        self.config = config
        self.client = None
        self._init_client()

    def _init_client(self):
        """Initialize Together client."""
        try:
            from together import Together
            self.client = Together()
            logger.info("Together client initialized")
        except ImportError:
            logger.error("Together package not installed. Run: pip install together")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Together client: {e}")
            logger.error("Ensure TOGETHER_API_KEY environment variable is set")
            raise

    def validate_file(self, file_path: str) -> bool:
        """Validate JSONL file format."""
        try:
            from together.utils import check_file
            report = check_file(file_path)

            if report.get('is_check_passed'):
                logger.info("File validation passed")
                return True
            else:
                logger.error(f"File validation failed: {report}")
                return False
        except Exception as e:
            logger.error(f"File validation error: {e}")
            return False

    def upload_file(self, file_path: str) -> str:
        """
        Upload training file to Together.ai.

        Returns:
            File ID for use in fine-tuning job
        """
        logger.info(f"Uploading file: {file_path}")

        response = self.client.files.upload(file_path, check=True)
        file_id = response.id

        logger.info(f"File uploaded successfully. ID: {file_id}")
        return file_id

    def create_job(self, training_file_id: str, validation_file_id: str = None) -> str:
        """
        Create a fine-tuning job.

        Args:
            training_file_id: ID of uploaded training file
            validation_file_id: Optional ID of validation file

        Returns:
            Job ID
        """
        logger.info(f"Creating fine-tuning job...")
        logger.info(f"  Model: {self.config.model}")
        logger.info(f"  Epochs: {self.config.n_epochs}")
        logger.info(f"  Learning rate: {self.config.learning_rate}")
        logger.info(f"  LoRA: {self.config.lora}")

        params = {
            "training_file": training_file_id,
            "model": self.config.model,
            "n_epochs": self.config.n_epochs,
            "learning_rate": self.config.learning_rate,
            "batch_size": self.config.batch_size,
            "warmup_ratio": self.config.warmup_ratio,
            "n_checkpoints": self.config.n_checkpoints,
            "train_on_inputs": self.config.train_on_inputs,
            "lora": self.config.lora,
            "suffix": self.config.suffix,
        }

        if self.config.lora:
            params["lora_r"] = self.config.lora_r
            params["lora_alpha"] = self.config.lora_alpha
            params["lora_dropout"] = self.config.lora_dropout

        if validation_file_id:
            params["validation_file"] = validation_file_id

        if self.config.wandb_project:
            params["wandb_project"] = self.config.wandb_project

        response = self.client.fine_tuning.create(**params)
        job_id = response.id

        logger.info(f"Fine-tuning job created. ID: {job_id}")
        return job_id

    def get_job_status(self, job_id: str) -> Dict:
        """Get status of a fine-tuning job."""
        response = self.client.fine_tuning.retrieve(job_id)
        return {
            "id": response.id,
            "status": response.status,
            "model": response.model,
            "output_name": getattr(response, 'output_name', None),
            "created_at": getattr(response, 'created_at', None),
        }

    def wait_for_completion(self, job_id: str, poll_interval: int = 60) -> Dict:
        """
        Wait for a fine-tuning job to complete.

        Args:
            job_id: Job ID to monitor
            poll_interval: Seconds between status checks

        Returns:
            Final job status
        """
        logger.info(f"Monitoring job {job_id}...")

        while True:
            status = self.get_job_status(job_id)
            current_status = status.get('status', 'unknown')

            logger.info(f"Job status: {current_status}")

            if current_status in ['STATUS_COMPLETED', 'completed']:
                logger.info("Job completed successfully!")
                return status
            elif current_status in ['STATUS_FAILED', 'failed', 'STATUS_CANCELLED', 'cancelled']:
                logger.error(f"Job failed with status: {current_status}")
                return status

            time.sleep(poll_interval)

    def list_jobs(self) -> List[Dict]:
        """List all fine-tuning jobs."""
        response = self.client.fine_tuning.list()
        return [
            {
                "id": job.id,
                "status": job.status,
                "model": job.model,
                "created_at": getattr(job, 'created_at', None)
            }
            for job in response.data
        ]

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running fine-tuning job."""
        try:
            self.client.fine_tuning.cancel(job_id)
            logger.info(f"Job {job_id} cancelled")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel job: {e}")
            return False

    def test_model(self, model_name: str, prompt: str, image_base64: str = None) -> str:
        """
        Test a fine-tuned model with inference.

        Args:
            model_name: Name of fine-tuned model (output_name from job)
            prompt: Text prompt
            image_base64: Optional base64 image for VLM

        Returns:
            Model response
        """
        messages = []

        if image_base64:
            # VLM format
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_base64}}
                ]
            })
        else:
            # LLM format
            messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=model_name,
            messages=messages,
            max_tokens=1024
        )

        return response.choices[0].message.content


# ============================================================================
# CONFIGURATION FILE HANDLING
# ============================================================================

def load_config(config_path: str) -> FinetuneConfig:
    """Load configuration from JSON file."""
    with open(config_path, 'r') as f:
        data = json.load(f)

    return FinetuneConfig(**data)


def save_config(config: FinetuneConfig, config_path: str):
    """Save configuration to JSON file."""
    with open(config_path, 'w') as f:
        json.dump(asdict(config), f, indent=2)


def create_default_config(output_path: str = "finetune_config.json"):
    """Create a default configuration file."""
    config = FinetuneConfig()
    save_config(config, output_path)
    logger.info(f"Default config saved to: {output_path}")
    return output_path


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Together.ai Fine-Tuning for Crafting VLM/LLM Models',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create default config file
  python together_finetune.py --create-config

  # Prepare data only (convert to JSONL)
  python together_finetune.py --prepare-only --input ./training_data/smithing_custom_data.json

  # Launch fine-tuning with default settings
  python together_finetune.py --input ./training_data/smithing_custom_data.json

  # Use custom config
  python together_finetune.py --config my_config.json --input ./training_data/

  # Monitor existing job
  python together_finetune.py --status <job-id>

  # List all jobs
  python together_finetune.py --list-jobs

Available Models:
  VLM (Vision):
    - meta-llama/Llama-3.2-11B-Vision-Instruct (default)
    - meta-llama/Llama-3.2-90B-Vision-Instruct
    - meta-llama/Llama-4-Scout-17B-16E-Instruct

  LLM (Text):
    - meta-llama/Meta-Llama-3.1-8B-Instruct
    - meta-llama/Meta-Llama-3.1-70B-Instruct
    - mistralai/Mixtral-8x7B-Instruct-v0.1
        """
    )

    # Input/Output
    parser.add_argument('--input', '-i', help='Input JSON training data file or directory')
    parser.add_argument('--output', '-o', help='Output JSONL file path')
    parser.add_argument('--config', '-c', help='Config JSON file path')

    # Actions
    parser.add_argument('--create-config', action='store_true', help='Create default config file')
    parser.add_argument('--prepare-only', action='store_true', help='Only prepare data, do not launch job')
    parser.add_argument('--list-jobs', action='store_true', help='List all fine-tuning jobs')
    parser.add_argument('--status', metavar='JOB_ID', help='Get status of a job')
    parser.add_argument('--cancel', metavar='JOB_ID', help='Cancel a running job')
    parser.add_argument('--wait', metavar='JOB_ID', help='Wait for job completion')

    # Model parameters
    parser.add_argument('--model', '-m', help='Base model for fine-tuning')
    parser.add_argument('--epochs', type=int, help='Number of training epochs')
    parser.add_argument('--learning-rate', type=float, help='Learning rate')
    parser.add_argument('--batch-size', type=int, help='Batch size')
    parser.add_argument('--suffix', help='Model suffix for identification')
    parser.add_argument('--no-lora', action='store_true', help='Disable LoRA (full fine-tuning)')

    args = parser.parse_args()

    # Create default config
    if args.create_config:
        create_default_config()
        return

    # Load config
    if args.config:
        config = load_config(args.config)
    else:
        config = FinetuneConfig()

    # Override config with command line args
    if args.model:
        config.model = args.model
    if args.epochs:
        config.n_epochs = args.epochs
    if args.learning_rate:
        config.learning_rate = args.learning_rate
    if args.batch_size:
        config.batch_size = args.batch_size
    if args.suffix:
        config.suffix = args.suffix
    if args.no_lora:
        config.lora = False

    # Job management commands (don't need input file)
    if args.list_jobs:
        tuner = TogetherFineTuner(config)
        jobs = tuner.list_jobs()
        print("\nFine-tuning Jobs:")
        print("-" * 80)
        for job in jobs:
            print(f"  {job['id']}: {job['status']} ({job['model']})")
        return

    if args.status:
        tuner = TogetherFineTuner(config)
        status = tuner.get_job_status(args.status)
        print(f"\nJob Status: {args.status}")
        print("-" * 40)
        for k, v in status.items():
            print(f"  {k}: {v}")
        return

    if args.cancel:
        tuner = TogetherFineTuner(config)
        tuner.cancel_job(args.cancel)
        return

    if args.wait:
        tuner = TogetherFineTuner(config)
        status = tuner.wait_for_completion(args.wait)
        print(f"\nFinal Status:")
        for k, v in status.items():
            print(f"  {k}: {v}")
        return

    # Main workflow: prepare data and optionally launch job
    if not args.input:
        parser.print_help()
        print("\nError: --input is required for data preparation/training")
        return

    # Convert data
    converter = DataConverter(config)
    jsonl_path = converter.convert_file(args.input, args.output)

    if args.prepare_only:
        print(f"\nData prepared successfully: {jsonl_path}")
        print("To launch fine-tuning, run without --prepare-only")
        return

    # Launch fine-tuning job
    print("\n" + "=" * 70)
    print("LAUNCHING FINE-TUNING JOB")
    print("=" * 70)

    tuner = TogetherFineTuner(config)

    # Validate file
    if not tuner.validate_file(jsonl_path):
        print("File validation failed. Please check the data format.")
        return

    # Upload file
    file_id = tuner.upload_file(jsonl_path)

    # Create job
    job_id = tuner.create_job(file_id)

    print(f"\nFine-tuning job started!")
    print(f"  Job ID: {job_id}")
    print(f"  Model: {config.model}")
    print(f"  Config: epochs={config.n_epochs}, lr={config.learning_rate}, lora={config.lora}")
    print(f"\nTo monitor: python together_finetune.py --status {job_id}")
    print(f"To wait:    python together_finetune.py --wait {job_id}")


if __name__ == "__main__":
    main()
