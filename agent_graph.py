import re
import sys
import os
from typing import TypedDict, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langgraph.graph import StateGraph, START, END
from tools import LoadCodeTool, RunTestsTool, ApplyPatchTool, ShowDiffTool, CodeAnalysisTool
import dotenv
dotenv.load_dotenv()
# --- 1. Define the typed state schema ---
class APRState(TypedDict):
    file_path: str
    original_code: str
    current_code: str
    error_line_no: int
    patch_line: str
    test_output: str
    tests_passed: bool
    attempts: int
    max_attempts: int
    success: bool
    error_message: str
    function_context: dict

# --- 2. Initialize tools and LLM ---
def initialize_tools_and_llm(root_dir: str = "Code-Refactoring-QuixBugs"):
    """Initialize all tools and the Gemini LLM"""
    load_tool = LoadCodeTool()
    test_tool = RunTestsTool(root_dir)
    patch_tool = ApplyPatchTool()
    diff_tool = ShowDiffTool()
    analysis_tool = CodeAnalysisTool()
    
    # Initialize Gemini with API key from environment
    gemini = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        temperature=0.1,
        max_tokens=512,
        google_api_key=os.getenv("GOOGLE_API_KEY")  # Make sure to set this environment variable
    )
    
    return load_tool, test_tool, patch_tool, diff_tool, analysis_tool, gemini

# --- 3. Enhanced helper functions ---
def extract_error_line_number(test_output: str) -> int:
    """Extract line number from test error output with multiple patterns"""
    patterns = [
        r"line (\d+)",
        r"File \"[^\"]+\", line (\d+)",
        r"Error on line (\d+)",
        r"at line (\d+)",
        r"Line (\d+):"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, test_output, re.IGNORECASE)
        if match:
            return int(match.group(1))
    
    # If no line number found, default to line 1
    return 1

def identify_error_type(test_output: str) -> str:
    """Identify the type of error from test output"""
    error_output_lower = test_output.lower()
    
    if "indexerror" in error_output_lower:
        return "Index Error (likely off-by-one or boundary issue)"
    elif "keyerror" in error_output_lower:
        return "Key Error (missing dictionary key)"
    elif "typeerror" in error_output_lower:
        return "Type Error (incorrect data type usage)"
    elif "valueerror" in error_output_lower:
        return "Value Error (invalid value)"
    elif "nameerror" in error_output_lower:
        return "Name Error (undefined variable)"
    elif "assertion" in error_output_lower:
        return "Logic Error (incorrect algorithm behavior)"
    elif "infinite" in error_output_lower or "timeout" in error_output_lower:
        return "Infinite Loop or Performance Issue"
    else:
        return "General Error"

def get_code_context(code: str, line_no: int, radius: int = 3) -> str:
    """Get code context around the error line with line numbers"""
    lines = code.splitlines()
    start_idx = max(0, line_no - 1 - radius)
    end_idx = min(len(lines), line_no + radius)
    
    context_lines = []
    for i in range(start_idx, end_idx):
        line_num = i + 1
        marker = ">>> " if line_num == line_no else "    "
        context_lines.append(f"{marker}{line_num:3d}: {lines[i]}")
    
    return "\n".join(context_lines)

# --- 4. Enhanced prompt template for Gemini ---
repair_prompt = PromptTemplate(
    input_variables=["function_context", "error_type", "code_context", "error_line", "test_output", "attempt_num"],
    template="""You are an expert Python debugging assistant specializing in algorithmic bug fixes.

CONTEXT:
- Function: {function_context}
- Error Type: {error_type}
- This is attempt #{attempt_num}

FAULTY CODE (line {error_line} marked with >>>):
```python
{code_context}
```

TEST FAILURE OUTPUT:
```
{test_output}
```

INSTRUCTIONS:
1. Analyze the error carefully - this is likely a QuixBugs algorithmic defect
2. Common QuixBugs issues: off-by-one errors, wrong operators, incorrect boundary conditions, missing edge cases
3. Focus on the EXACT line marked with >>> - provide only the corrected version of that line
4. Maintain the same indentation and code style
5. Do not add explanations, comments, or multiple lines

RESPONSE FORMAT:
Provide ONLY the corrected line {error_line} with proper indentation:"""
)

# --- 5. Define LangGraph nodes ---
def load_code_node(state: APRState) -> APRState:
    """Load the original source code"""
    try:
        load_tool, _, _, _, _, _ = initialize_tools_and_llm()
        code = load_tool(state['file_path'])
        return {
            **state,
            'original_code': code,
            'current_code': code,
            'error_message': ''
        }
    except Exception as e:
        return {
            **state,
            'error_message': f"Failed to load code: {str(e)}",
            'success': False
        }

def localize_defect_node(state: APRState) -> APRState:
    """Run tests and localize the defect"""
    try:
        _, test_tool, _, _, analysis_tool, _ = initialize_tools_and_llm()
        
        # Run tests
        test_output = test_tool(state['file_path'])
        
        # Extract error line
        error_line = extract_error_line_number(test_output)
        
        # Get function context
        function_context = analysis_tool.get_function_context(state['current_code'], error_line)
        
        return {
            **state,
            'test_output': test_output,
            'error_line_no': error_line,
            'function_context': function_context,
            'tests_passed': 'FAIL' not in test_output.upper() and 'ERROR' not in test_output.upper()
        }
    except Exception as e:
        return {
            **state,
            'error_message': f"Failed to localize defect: {str(e)}",
            'success': False
        }

def generate_patch_node(state: APRState) -> APRState:
    """Generate a patch using Gemini"""
    try:
        _, _, _, _, _, gemini = initialize_tools_and_llm()
        
        # Prepare context information
        error_type = identify_error_type(state['test_output'])
        code_context = get_code_context(state['current_code'], state['error_line_no'])
        function_name = state['function_context'].get('function_name', 'unknown')
        
        # Generate patch using enhanced prompt
        prompt_input = {
            'function_context': f"Function '{function_name}'" if function_name != 'unknown' else "Code section",
            'error_type': error_type,
            'code_context': code_context,
            'error_line': state['error_line_no'],
            'test_output': state['test_output'][-500:],  # Last 500 chars to avoid token limits
            'attempt_num': state['attempts'] + 1
        }
        
        response = gemini.invoke(repair_prompt.format(**prompt_input))
        patch_line = response.content.strip()
        
        # Clean up the response - remove any extra formatting
        if '```' in patch_line:
            # Extract code from markdown blocks
            lines = patch_line.split('\n')
            for line in lines:
                if line.strip() and not line.strip().startswith('```'):
                    patch_line = line
                    break
        
        return {
            **state,
            'patch_line': patch_line,
            'attempts': state['attempts'] + 1
        }
    except Exception as e:
        return {
            **state,
            'error_message': f"Failed to generate patch: {str(e)}",
            'success': False
        }

def apply_patch_node(state: APRState) -> APRState:
    """Apply the generated patch"""
    try:
        _, _, patch_tool, _, _, _ = initialize_tools_and_llm()
        
        # Apply the patch
        patched_code = patch_tool(state['file_path'], state['error_line_no'], state['patch_line'])
        
        return {
            **state,
            'current_code': patched_code
        }
    except Exception as e:
        return {
            **state,
            'error_message': f"Failed to apply patch: {str(e)}",
            'success': False
        }

def validate_patch_node(state: APRState) -> APRState:
    """Run tests to validate the patch"""
    try:
        _, test_tool, _, _, _, _ = initialize_tools_and_llm()
        
        # Run tests on patched code
        test_output = test_tool(state['file_path'])
        tests_passed = 'FAIL' not in test_output.upper() and 'ERROR' not in test_output.upper()
        
        return {
            **state,
            'test_output': test_output,
            'tests_passed': tests_passed
        }
    except Exception as e:
        return {
            **state,
            'error_message': f"Failed to validate patch: {str(e)}",
            'success': False
        }

def finish_success_node(state: APRState) -> APRState:
    """Handle successful repair"""
    try:
        _, _, _, diff_tool, _, _ = initialize_tools_and_llm()
        
        # Generate diff
        diff = diff_tool(state['original_code'], state['current_code'], 
                        os.path.basename(state['file_path']))
        
        print("\n" + "="*60)
        print("🎉 REPAIR SUCCESSFUL!")
        print("="*60)
        print(f"File: {state['file_path']}")
        print(f"Attempts: {state['attempts']}")
        print(f"Error Line: {state['error_line_no']}")
        print(f"\nFinal Patch Applied:")
        print(f"  Line {state['error_line_no']}: {state['patch_line'].strip()}")
        print(f"\nUnified Diff:")
        print(diff)
        print("="*60)
        
        return {
            **state,
            'success': True
        }
    except Exception as e:
        return {
            **state,
            'error_message': f"Error in success handler: {str(e)}",
            'success': False
        }

def finish_failure_node(state: APRState) -> APRState:
    """Handle failed repair"""
    error_type = identify_error_type(state['test_output'])
    
    print("\n" + "="*60)
    print("❌ REPAIR FAILED")
    print("="*60)
    print(f"File: {state['file_path']}")
    print(f"Attempts: {state['attempts']}/{state['max_attempts']}")
    print(f"Error Line: {state['error_line_no']}")
    print(f"Error Type: {error_type}")
    print(f"\nLast Error Output:")
    print(state['test_output'][-300:])  # Last 300 chars
    
    if state.get('error_message'):
        print(f"\nSystem Error: {state['error_message']}")
    
    print("\n💡 Suggested Manual Investigation:")
    print("- Check for off-by-one errors in loops and array access")
    print("- Verify boundary conditions and edge cases")
    print("- Look for incorrect operators (==, !=, <, <=, >, >=)")
    print("- Check variable initialization and scope")
    print("="*60)
    
    return {
        **state,
        'success': False
    }

# --- 6. Define routing logic ---
def should_continue_repair(state: APRState) -> str:
    """Determine next step based on current state"""
    if state.get('error_message'):
        return "finish_failure"
    elif state['tests_passed']:
        return "finish_success"
    elif state['attempts'] >= state['max_attempts']:
        return "finish_failure"
    else:
        return "generate_patch"

# --- 7. Build the StateGraph ---
def create_apr_graph():
    """Create and configure the APR workflow graph"""
    
    workflow = StateGraph(APRState)
    
    # Add nodes
    workflow.add_node("load_code", load_code_node)
    workflow.add_node("localize_defect", localize_defect_node)
    workflow.add_node("generate_patch", generate_patch_node)
    workflow.add_node("apply_patch", apply_patch_node)
    workflow.add_node("validate_patch", validate_patch_node)
    workflow.add_node("finish_success", finish_success_node)
    workflow.add_node("finish_failure", finish_failure_node)
    
    # Define edges
    workflow.add_edge(START, "load_code")
    workflow.add_edge("load_code", "localize_defect")
    workflow.add_edge("localize_defect", "generate_patch")
    workflow.add_edge("generate_patch", "apply_patch")
    workflow.add_edge("apply_patch", "validate_patch")
    
    # Conditional edge for retry logic
    workflow.add_conditional_edges(
        "validate_patch",
        should_continue_repair,
        {
            "generate_patch": "generate_patch",
            "finish_success": "finish_success",
            "finish_failure": "finish_failure"
        }
    )
    
    workflow.add_edge("finish_success", END)
    workflow.add_edge("finish_failure", END)
    
    return workflow.compile()

# --- 8. Main execution ---
def main():
    """Main execution function"""
    if len(sys.argv) != 2:
        print("Usage: python agent_graph.py <buggy_file.py>")
        print("Example: python agent_graph.py breadth_first_search.py")
        sys.exit(1)
    
    # Check if GOOGLE_API_KEY is set
    if not os.getenv("GOOGLE_API_KEY"):
        print("Error: Please set the GOOGLE_API_KEY environment variable")
        print("You can get a free API key from: https://makersuite.google.com/app/apikey")
        sys.exit(1)
    
    # Get the filename and construct the full path
    filename = sys.argv[1]
    if not filename.endswith('.py'):
        filename += '.py'
    
    root_dir = "Code-Refactoring-QuixBugs"
    file_path = os.path.join(root_dir, "python_programs", filename)
    
    # Check if file exists
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        print(f"Available files in python_programs/:")
        try:
            programs_dir = os.path.join(root_dir, "python_programs")
            if os.path.exists(programs_dir):
                for f in sorted(os.listdir(programs_dir)):
                    if f.endswith('.py'):
                        print(f"  - {f}")
        except:
            pass
        sys.exit(1)
    
    # Initialize state
    initial_state: APRState = {
        'file_path': file_path,
        'original_code': '',
        'current_code': '',
        'error_line_no': 0,
        'patch_line': '',
        'test_output': '',
        'tests_passed': False,
        'attempts': 0,
        'max_attempts': 3,
        'success': False,
        'error_message': '',
        'function_context': {}
    }
    
    print(f"🔧 Starting Automated Program Repair for: {filename}")
    print(f"📁 Full path: {file_path}")
    print("-" * 60)
    
    # Create and run the graph
    app = create_apr_graph()
    
    try:
        final_state = app.invoke(initial_state)
        
        # Print final result
        if final_state['success']:
            print(f"\n✅ Repair completed successfully in {final_state['attempts']} attempts!")
        else:
            print(f"\n❌ Repair failed after {final_state['attempts']} attempts.")
            
    except Exception as e:
        print(f"\n💥 Unexpected error during repair: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()