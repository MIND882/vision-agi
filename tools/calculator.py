# tools/calculator.py
# ============================================================
# Calculator Tool — safe math evaluation.
# Uses Python's ast module — NO eval() for security.
# ============================================================

import ast
import math
import operator


# Safe operators allowed
SAFE_OPERATORS = {
    ast.Add:  operator.add,
    ast.Sub:  operator.sub,
    ast.Mult: operator.mul,
    ast.Div:  operator.truediv,
    ast.Pow:  operator.pow,
    ast.Mod:  operator.mod,
    ast.USub: operator.neg,
}

# Safe math functions allowed
SAFE_FUNCTIONS = {
    "sqrt": math.sqrt, "log": math.log,   "log10": math.log10,
    "sin":  math.sin,  "cos": math.cos,   "tan":   math.tan,
    "abs":  abs,       "round": round,    "ceil":  math.ceil,
    "floor": math.floor, "pi": math.pi,   "e":     math.e,
}


def _safe_eval(node):
    """Recursively evaluate AST node safely."""
    if isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.BinOp):
        op = SAFE_OPERATORS.get(type(node.op))
        if not op:
            raise ValueError(f"Operator not allowed: {node.op}")
        return op(_safe_eval(node.left), _safe_eval(node.right))
    elif isinstance(node, ast.UnaryOp):
        op = SAFE_OPERATORS.get(type(node.op))
        if not op:
            raise ValueError(f"Operator not allowed: {node.op}")
        return op(_safe_eval(node.operand))
    elif isinstance(node, ast.Call):
        func_name = node.func.id if isinstance(node.func, ast.Name) else None
        if func_name not in SAFE_FUNCTIONS:
            raise ValueError(f"Function not allowed: {func_name}")
        args = [_safe_eval(a) for a in node.args]
        return SAFE_FUNCTIONS[func_name](*args)
    elif isinstance(node, ast.Name):
        if node.id in SAFE_FUNCTIONS:
            return SAFE_FUNCTIONS[node.id]
        raise ValueError(f"Name not allowed: {node.id}")
    else:
        raise ValueError(f"Expression type not allowed: {type(node)}")


def calculator(expression: str) -> str:
    """
    Safely evaluate a math expression.

    Examples:
        calculator("2 + 2")           → "4"
        calculator("sqrt(144)")       → "12.0"
        calculator("2 ** 10")         → "1024"
        calculator("sin(pi / 2)")     → "1.0"
    """
    try:
        # Clean up expression
        expr = expression.strip().replace("^", "**")
        tree = ast.parse(expr, mode="eval")
        result = _safe_eval(tree.body)

        # Format result cleanly
        if isinstance(result, float) and result.is_integer():
            return str(int(result))
        return str(round(result, 10))

    except ZeroDivisionError:
        return "Error: Division by zero"
    except Exception as e:
        return f"Calculation error: {str(e)}\nExpression: {expression}"