# tools/code_executor.py
# ============================================================
# Code Executor Tool — runs Python code in a subprocess sandbox.
# Timeout enforced. No network/file access in future (Phase 2).
# ============================================================

import subprocess
import sys
import textwrap


def code_executor(code: str, timeout: int = 10) -> str:
    """
    Execute Python code safely in a subprocess.

    Args:
        code    : Python code string to execute
        timeout : Max seconds to run (default 10)

    Returns:
        stdout output or error message
    """
    try:
        # Dedent in case LLM added extra indentation
        clean_code = textwrap.dedent(code).strip()

        result = subprocess.run(
            [sys.executable, "-c", clean_code],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode == 0:
            output = result.stdout.strip()
            return output if output else "Code executed successfully (no output)"
        else:
            error = result.stderr.strip()
            return f"Code execution error:\n{error}"

    except subprocess.TimeoutExpired:
        return f"Code execution timed out after {timeout} seconds"
    except Exception as e:
        return f"Execution failed: {str(e)}"