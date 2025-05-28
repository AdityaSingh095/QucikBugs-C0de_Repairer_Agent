import subprocess
import difflib
import os
import sys

class LoadCodeTool:
    """Tool to load Python source code from file"""
    
    def __call__(self, path: str) -> str:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"Could not find file: {path}")
        except Exception as e:
            raise Exception(f"Error reading file {path}: {str(e)}")

class RunTestsTool:
    """Tool to run QuixBugs test harness and capture output"""
    
    def __init__(self, root_dir: str = "Code-Refactoring-QuixBugs"):
        self.root_dir = root_dir
        self.tester_path = os.path.join(root_dir, "tester.py")
        
    def __call__(self, file_path: str) -> str:
        """Run tests for a specific Python file"""
        try:
            # Extract just the filename from the full path
            filename = os.path.basename(file_path)
            
            # Run the tester with the filename
            result = subprocess.run(
                [sys.executable, self.tester_path, filename],
                cwd=self.root_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            output = result.stdout + result.stderr
            return output if output.strip() else "No test output generated"
            
        except subprocess.TimeoutExpired:
            return "ERROR: Test execution timed out after 30 seconds"
        except Exception as e:
            return f"ERROR: Failed to run tests - {str(e)}"

class ApplyPatchTool:
    """Tool to apply a single-line patch to a Python file"""
    
    def __call__(self, file_path: str, line_no: int, new_line: str) -> str:
        """Apply patch and return the modified code"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            if line_no < 1 or line_no > len(lines):
                raise ValueError(f"Line number {line_no} is out of range (1-{len(lines)})")
            
            # Preserve original indentation if new line doesn't specify it
            original_line = lines[line_no - 1]
            original_indent = len(original_line) - len(original_line.lstrip())
            
            # Apply indentation to new line if it doesn't have proper indentation
            if new_line.strip() and not new_line.startswith(' ' * original_indent):
                new_line = ' ' * original_indent + new_line.strip()
            
            # Ensure line ends with newline
            if not new_line.endswith('\n'):
                new_line += '\n'
            
            lines[line_no - 1] = new_line
            
            # Write back to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            
            return ''.join(lines)
            
        except Exception as e:
            raise Exception(f"Error applying patch to {file_path} at line {line_no}: {str(e)}")

class ShowDiffTool:
    """Tool to generate unified diff between two code versions"""
    
    def __call__(self, old_code: str, new_code: str, filename: str = "file.py") -> str:
        """Generate unified diff"""
        try:
            diff = difflib.unified_diff(
                old_code.splitlines(keepends=True),
                new_code.splitlines(keepends=True),
                fromfile=f"{filename} (original)",
                tofile=f"{filename} (patched)",
                lineterm=''
            )
            return ''.join(diff)
        except Exception as e:
            return f"Error generating diff: {str(e)}"

class CodeAnalysisTool:
    """Tool to analyze code structure and provide context"""
    
    def get_function_context(self, code: str, line_no: int) -> dict:
        """Get context about the function containing the error line"""
        lines = code.splitlines()
        
        # Find the function containing this line
        function_start = None
        function_name = None
        
        for i in range(line_no - 1, -1, -1):
            line = lines[i].strip()
            if line.startswith('def '):
                function_start = i + 1
                function_name = line.split('(')[0].replace('def ', '').strip()
                break
        
        # Get surrounding context
        context_start = max(0, line_no - 5)
        context_end = min(len(lines), line_no + 5)
        context_lines = lines[context_start:context_end]
        
        return {
            'function_name': function_name,
            'function_start_line': function_start,
            'error_line': line_no,
            'context_lines': context_lines,
            'context_start_line': context_start + 1
        }