"""
Strategy Coder

Generates executable Zipline strategy code from trading hypotheses.
"""

import ast
from dataclasses import dataclass
from typing import Optional, Any
from pathlib import Path


@dataclass
class StrategyCode:
    """Container for generated strategy code."""
    
    hypothesis_id: str
    code: str
    dependencies: list[str]
    config: dict[str, Any]
    validated: bool = False
    validation_errors: Optional[str] = None


class StrategyCoder:
    """Generates and validates Zipline strategy code."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        """
        Initialize the strategy coder.
        
        Args:
            api_key: Optional API key for LLM provider. If None, reads from environment.
            model: LLM model to use for code generation.
        """
        self.api_key = api_key
        self.model = model
        self.templates: dict[str, str] = {}
        self._load_templates()
    
    def _load_templates(self) -> None:
        """Load strategy code templates."""
        # Placeholder for future template loading
        pass
    
    def generate_strategy_code(
        self, 
        hypothesis: dict[str, Any], 
        template: str = "basic"
    ) -> StrategyCode:
        """
        Generate strategy code from hypothesis.
        
        Args:
            hypothesis: Trading hypothesis dictionary
            template: Template type to use
            
        Returns:
            StrategyCode object with generated code
        """
        # Placeholder - will be implemented by LangGraph nodes
        return StrategyCode(
            hypothesis_id=hypothesis.get("id", "unknown"),
            code="",
            dependencies=["zipline", "pandas"],
            config={}
        )
    
    def validate_code(self, code: str) -> tuple[bool, Optional[str]]:
        """
        Validate Python syntax of generated code using AST parser.
        
        Args:
            code: Python code string to validate
            
        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if syntax is valid, False otherwise
            - error_message: None if valid, error description if invalid
        """
        try:
            ast.parse(code)
            return True, None
        except SyntaxError as e:
            error_msg = f"Syntax error at line {e.lineno}: {e.msg}"
            if e.text:
                error_msg += f"\n  {e.text.strip()}"
                if e.offset:
                    error_msg += f"\n  {' ' * (e.offset - 1)}^"
            return False, error_msg
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    def validate_strategy_code(self, strategy_code: StrategyCode) -> bool:
        """
        Validate a StrategyCode object and update its validation status.
        
        Args:
            strategy_code: StrategyCode object to validate
            
        Returns:
            True if valid, False otherwise
        """
        is_valid, error_msg = self.validate_code(strategy_code.code)
        strategy_code.validated = is_valid
        strategy_code.validation_errors = error_msg
        return is_valid
    
    def refactor_code(
        self, 
        strategy_code: StrategyCode, 
        improvements: list[str]
    ) -> StrategyCode:
        """
        Refactor code based on improvement suggestions.
        
        Args:
            strategy_code: Current strategy code
            improvements: List of improvement suggestions
            
        Returns:
            New StrategyCode with refactored code
        """
        # Placeholder - will be implemented by refinement agent
        return strategy_code
    
    def export_to_file(self, strategy_code: StrategyCode, filepath: str) -> None:
        """
        Export strategy code to a Python file.
        
        Args:
            strategy_code: StrategyCode object to export
            filepath: Path where to save the file
        """
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(strategy_code.code, encoding="utf-8")
