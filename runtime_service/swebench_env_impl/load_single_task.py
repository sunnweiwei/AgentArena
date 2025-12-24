#!/usr/bin/env python3
"""
Test a single SWE-bench task by instance_id.

This script allows you to test a specific task by providing its instance_id.
It creates a temporary instance file and runs the evaluation for that single task.

Usage:
    uv run python -m benchmarks.swebench.test_single_task <instance_id> <llm_config_path> [options]
    
Examples:
    # Basic usage with default settings
    uv run python -m benchmarks.swebench.test_single_task django__django-11333 .llm_config/sonnet-4-5.json
    
    # With custom workspace and iterations
    uv run python -m benchmarks.swebench.test_single_task django__django-11333 .llm_config/sonnet-4-5.json \
        --workspace docker --max-iterations 200
    
    # With remote workspace
    uv run python -m benchmarks.swebench.test_single_task django__django-11333 .llm_config/sonnet-4-5.json \
        --workspace remote
    
    # Run evaluation after inference
    uv run python -m benchmarks.swebench.test_single_task django__django-11333 .llm_config/sonnet-4-5.json \
        --run-eval
"""

import argparse
import os
import sys
import tempfile
from pathlib import Path

from benchmarks.swebench.run_infer import SWEBenchEvaluation
from benchmarks.utils.evaluation_utils import (
    construct_eval_output_dir,
    get_default_on_result_writer,
)
from benchmarks.utils.models import EvalMetadata
from openhands.sdk import LLM, get_logger

logger = get_logger(__name__)


def test_single_task(
    instance_id: str,
    llm_config_path: str,
    dataset: str = "princeton-nlp/SWE-bench_Verified",
    split: str = "test",
    workspace_type: str = "docker",
    max_iterations: int = 100,
    output_dir: str = "./eval_outputs",
    note: str = "single_task_test",
    prompt_path: str | None = None,
    run_eval: bool = False,
    max_attempts: int = 3,
    max_retries: int = 3,
    **kwargs,
) -> None:
    """
    Test a single SWE-bench task by instance_id.
    
    Args:
        instance_id: The instance ID to test (e.g., "django__django-11333")
        llm_config_path: Path to LLM configuration JSON file
        dataset: Dataset name (default: "princeton-nlp/SWE-bench_Verified")
        split: Dataset split (default: "test")
        workspace_type: Type of workspace ("docker" or "remote")
        max_iterations: Maximum iterations for the agent
        output_dir: Output directory for results
        note: Evaluation note
        prompt_path: Path to prompt template (optional)
        run_eval: Whether to run evaluation after inference
        max_attempts: Maximum number of attempts for iterative mode
        max_retries: Maximum retries for instances that throw exceptions
        **kwargs: Additional arguments passed to metadata
    """
    # Validate LLM config
    if not os.path.isfile(llm_config_path):
        raise ValueError(f"LLM config file {llm_config_path} does not exist")
    
    with open(llm_config_path, "r") as f:
        llm_config = f.read()
    llm = LLM.model_validate_json(llm_config)
    logger.info("Using LLM config: %s", llm.model_dump_json(indent=2))
    
    # Create a temporary file with the single instance_id
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(f"{instance_id}\n")
        temp_instance_file = f.name
    
    try:
        # Set up prompt path
        if prompt_path is None:
            prompt_dir = (Path(__file__).parent.parent.parent/ "benchmarks" / "benchmarks" / "swebench" / "prompts").resolve()
            default_prompt_path = prompt_dir / "default.j2"
            if not default_prompt_path.exists():
                raise FileNotFoundError(
                    f"Default prompt {default_prompt_path} not found"
                )
            prompt_path = str(default_prompt_path)
        
        # Construct output directory
        dataset_description = dataset.replace("/", "__") + "-" + split.replace("/", "__")
        structured_output_dir = construct_eval_output_dir(
            base_dir=output_dir,
            dataset_name=dataset_description,
            model_name=llm.model,
            max_iterations=max_iterations,
            eval_note=note,
        )
        
        # Create metadata
        from openhands.sdk.critic import PassCritic
        
        # Use PassCritic as default (always accepts output, suitable for single-attempt runs)
        critic = PassCritic()
        
        metadata = EvalMetadata(
            llm=llm,
            dataset=dataset,
            dataset_split=split,
            max_iterations=max_iterations,
            eval_output_dir=structured_output_dir,
            details={},
            prompt_path=prompt_path,
            eval_limit=1,  # Only one instance
            env_setup_commands=["export PIP_CACHE_DIR=~/.cache/pip"],
            max_attempts=max_attempts,
            critic=critic,
            selected_instances_file=temp_instance_file,
            max_retries=max_retries,
            workspace_type=workspace_type,
        )
        
        # Run evaluation
        logger.info(f"Testing instance: {instance_id}")
        evaluator = SWEBenchEvaluation(metadata=metadata, num_workers=1)
        
        evaluator.run(on_result=get_default_on_result_writer(evaluator.output_path))
        
        logger.info(f"Evaluation completed! Results saved to: {evaluator.output_path}")
        
        # Optionally run evaluation
        if run_eval:
            logger.info("Running SWE-bench evaluation...")
            from benchmarks.swebench.eval_infer import (
                convert_to_swebench_format,
                run_swebench_evaluation,
            )
            
            # Convert to SWE-bench format
            output_file = Path(evaluator.output_path)
            swebench_output = output_file.with_suffix(".swebench.jsonl")
            convert_to_swebench_format(
                str(output_file), str(swebench_output), model_name="openhands"
            )
            
            # Run evaluation
            run_swebench_evaluation(str(swebench_output), dataset=dataset)
            
            logger.info("SWE-bench evaluation completed!")
    
    finally:
        # Clean up temporary file
        if os.path.exists(temp_instance_file):
            os.unlink(temp_instance_file)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test a single SWE-bench task by instance_id",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    
    parser.add_argument(
        "instance_id",
        type=str,
        help="The instance ID to test (e.g., 'django__django-11333')",
    )
    parser.add_argument(
        "llm_config_path",
        type=str,
        help="Path to JSON LLM configuration file",
    )
    
    # Add common arguments
    parser.add_argument(
        "--dataset",
        type=str,
        default="princeton-nlp/SWE-bench_Verified",
        help="Dataset name (default: princeton-nlp/SWE-bench_Verified)",
    )
    parser.add_argument(
        "--split",
        type=str,
        default="test",
        help="Dataset split (default: test)",
    )
    parser.add_argument(
        "--workspace",
        type=str,
        default="docker",
        choices=["docker", "remote"],
        help="Type of workspace to use (default: docker)",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=100,
        help="Maximum iterations (default: 100)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./eval_outputs",
        help="Evaluation output directory (default: ./eval_outputs)",
    )
    parser.add_argument(
        "--note",
        type=str,
        default="single_task_test",
        help="Evaluation note (default: single_task_test)",
    )
    parser.add_argument(
        "--prompt-path",
        type=str,
        default=None,
        help="Path to prompt template file (default: prompts/default.j2)",
    )
    parser.add_argument(
        "--run-eval",
        action="store_true",
        help="Run SWE-bench evaluation after inference",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=3,
        help="Maximum number of attempts for iterative mode (default: 3)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum retries for instances that throw exceptions (default: 3)",
    )
    
    args = parser.parse_args()
    
    # Validate max_attempts
    if args.max_attempts < 1:
        raise ValueError(f"max_attempts must be >= 1, got {args.max_attempts}")
    
    try:
        test_single_task(
            instance_id=args.instance_id,
            llm_config_path=args.llm_config_path,
            dataset=args.dataset,
            split=args.split,
            workspace_type=args.workspace,
            max_iterations=args.max_iterations,
            output_dir=args.output_dir,
            note=args.note,
            prompt_path=args.prompt_path,
            run_eval=args.run_eval,
            max_attempts=args.max_attempts,
            max_retries=args.max_retries,
        )
        logger.info("Test completed successfully!")
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

